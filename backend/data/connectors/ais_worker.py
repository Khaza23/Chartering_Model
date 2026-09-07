"""AISStream WebSocket client for $0 real-time vessel & port congestion tracking.

Free service with GitHub login (aisstream.io/account).
Subscribes ONLY to 4 tight bounding boxes around the 5 Indian bulk ports:
- Paradip & Dhamra (East Coast)
- Vizag & Gangavaram (East Coast)
- Mundra (West Coast)

Extracts:
1. PositionReport: speed < 0.5 kn + nav_status at-anchor -> counts towards port waiting queue
2. ShipStaticData: destination, ETA, draught for tracked MMSIs -> updates Vessel table live fields

Runs in a non-blocking background thread/task. Fails soft if AISSTREAM_KEY is not set.
"""

import asyncio
import json
import os
import threading
import time
from datetime import date, datetime
from typing import Dict, List, Optional

try:
    import websockets
except ImportError:
    websockets = None

# Bounding boxes format: [[[lat_top_left, lon_top_left], [lat_bottom_right, lon_bottom_right]], ...]
PORT_BBOXES = {
    "Paradip": [[20.45, 86.50], [20.15, 86.85]],
    "Dhamra": [[20.95, 86.80], [20.65, 87.15]],
    "Gangavaram": [[17.70, 83.10], [17.50, 83.35]],
    "Vizag": [[17.80, 83.20], [17.60, 83.40]],
    "Mundra": [[22.90, 69.55], [22.60, 69.85]],
}

# Thread-safe in-memory state aggregated across the current hour
_state_lock = threading.Lock()
_port_waiting_ships: Dict[str, set] = {p: set() for p in PORT_BBOXES}
_vessel_positions: Dict[str, dict] = {}
_is_running = False
_last_msg_time: Optional[float] = None


def is_in_bbox(lat: float, lon: float, bbox: List[List[float]]) -> bool:
    top_lat, left_lon = bbox[0]
    bot_lat, right_lon = bbox[1]
    return min(top_lat, bot_lat) <= lat <= max(top_lat, bot_lat) and \
           min(left_lon, right_lon) <= lon <= max(left_lon, right_lon)


def get_port_for_coord(lat: float, lon: float) -> Optional[str]:
    for port, bbox in PORT_BBOXES.items():
        if is_in_bbox(lat, lon, bbox):
            return port
    return None


async def _ais_consumer_loop(api_key: str, tracked_mmsis: List[str]):
    global _last_msg_time
    url = "wss://stream.aisstream.io/v0/stream"

    # Combine unique bboxes
    bboxes = list(PORT_BBOXES.values())

    sub_msg = {
        "APIKey": api_key,
        "BoundingBoxes": bboxes,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"]
    }
    if tracked_mmsis:
        sub_msg["FiltersShipMMSI"] = [str(m) for m in tracked_mmsis if m]

    while _is_running:
        try:
            print("[AIS] Connecting to aisstream.io...")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps(sub_msg))
                print("[AIS] Connected and subscribed to port bounding boxes.")

                async for message_str in ws:
                    if not _is_running:
                        break
                    _last_msg_time = time.time()
                    try:
                        msg = json.loads(message_str)
                        mtype = msg.get("MessageType")
                        metadata = msg.get("MetaData", {})
                        mmsi = str(metadata.get("MMSI", ""))
                        ship_name = metadata.get("ShipName", "")

                        if mtype == "PositionReport":
                            pos = msg.get("Message", {}).get("PositionReport", {})
                            lat = pos.get("Latitude")
                            lon = pos.get("Longitude")
                            sog = pos.get("Sog", 0.0)  # Speed over ground in knots
                            nav_status = pos.get("NavigationalStatus", -1)

                            if lat is not None and lon is not None:
                                port_hit = get_port_for_coord(lat, lon)
                                with _state_lock:
                                    if mmsi:
                                        _vessel_positions[mmsi] = {
                                            "mmsi": mmsi,
                                            "name": ship_name,
                                            "lat": lat,
                                            "lon": lon,
                                            "sog": sog,
                                            "last_ais_at": datetime.utcnow(),
                                            "port": port_hit
                                        }
                                    # speed < 0.8 knots or nav status 1 (at anchor) or 5 (moored)
                                    if port_hit and (sog < 0.8 or nav_status in [1, 5]):
                                        _port_waiting_ships[port_hit].add(mmsi or f"{lat:.3f},{lon:.3f}")

                        elif mtype == "ShipStaticData":
                            static = msg.get("Message", {}).get("ShipStaticData", {})
                            dest = static.get("Destination", "")
                            eta = static.get("Eta", {})
                            imo = static.get("ImoNumber", 0)
                            with _state_lock:
                                if mmsi in _vessel_positions:
                                    _vessel_positions[mmsi].update({
                                        "destination_raw": dest,
                                        "eta_raw": str(eta),
                                        "imo": str(imo) if imo else None
                                    })

                    except Exception as parse_err:
                        pass
        except Exception as conn_err:
            print(f"[AIS] Connection dropped: {conn_err}. Reconnecting in 15s...")
            await asyncio.sleep(15)


def _worker_thread_main(api_key: str, tracked_mmsis: List[str]):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_ais_consumer_loop(api_key, tracked_mmsis))
    finally:
        loop.close()


def start_ais_worker(tracked_mmsis: Optional[List[str]] = None) -> bool:
    """Spawns the background daemon thread if AISSTREAM_KEY is set and websockets is available."""
    global _is_running
    api_key = os.getenv("AISSTREAM_KEY", "").strip()
    if not api_key:
        print("[AIS] No AISSTREAM_KEY configured — live AIS worker skipped (will use database history).")
        return False
    if websockets is None:
        print("[AIS] websockets package not installed — live AIS worker skipped.")
        return False
    if _is_running:
        return True

    _is_running = True
    t = threading.Thread(
        target=_worker_thread_main,
        args=(api_key, tracked_mmsis or []),
        daemon=True,
        name="AISStreamWorker"
    )
    t.start()
    print("[AIS] Background worker thread started.")
    return True


def stop_ais_worker():
    global _is_running
    _is_running = False


def get_live_port_metrics() -> Dict[str, dict]:
    """Returns snapshot of current waiting counts & congestion index for each port."""
    with _state_lock:
        metrics = {}
        # Nominal berth capacities
        caps = {"Paradip": 8, "Dhamra": 6, "Gangavaram": 10, "Vizag": 12, "Mundra": 15}
        for port, ships in _port_waiting_ships.items():
            waiting_count = len(ships)
            cap = caps.get(port, 8)
            # Congestion index 0-100 bounded
            idx = min(100.0, (waiting_count / max(1, cap)) * 60.0 + 15.0)
            delay = round(idx * 0.4 + 4.0, 1)
            metrics[port] = {
                "port_name": port,
                "vessels_waiting": waiting_count,
                "congestion_index": round(idx, 1),
                "expected_delay_hours": delay,
                "date": date.today(),
                "source": "live/aisstream"
            }
        return metrics


def get_live_vessel_updates() -> List[dict]:
    """Returns all tracked vessel updates gathered since start."""
    with _state_lock:
        return list(_vessel_positions.values())
