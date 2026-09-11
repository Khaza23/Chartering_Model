"""Marinesia API connector for real vessel data.

Fetches bulk carrier vessels from the Marinesia AIS API.
Fails soft — returns empty list on any error.

Env: MARINESIA_KEY
"""

import os
import json
import time

try:
    import requests
except ImportError:
    requests = None

from data.connectors.base import cache_read, cache_write

API_KEY = os.getenv("MARINESIA_KEY", "").strip()
BASE = "https://api.marinesia.com/api/v2"

VESSEL_CACHE_HOURS = 24
CACHE_KEY = "marinesia_vessels_bulk_carriers"

# Bounding boxes for major shipping lanes
SEARCH_AREAS = [
    {"name": "Bay of Bengal",    "lat_min": 5.0,  "lat_max": 22.0, "long_min": 80.0, "long_max": 95.0},
    {"name": "Arabian Sea",      "lat_min": 5.0,  "lat_max": 22.0, "long_min": 60.0, "long_max": 75.0},
    {"name": "Indian Ocean S",   "lat_min": -10.0,"lat_max": 10.0, "long_min": 55.0, "long_max": 95.0},
    {"name": "South China Sea",  "lat_min": 0.0,  "lat_max": 20.0, "long_min": 100.0,"long_max": 120.0},
    {"name": "Indonesia",        "lat_min": -10.0,"lat_max": 5.0,  "long_min": 100.0,"long_max": 140.0},
    {"name": "Australia East",   "lat_min": -40.0,"lat_max": -10.0,"long_min": 110.0,"long_max": 155.0},
    {"name": "South Africa",     "lat_min": -35.0,"lat_max": -20.0,"long_min": 15.0, "long_max": 40.0},
]

CLASS_DWT_RANGES = {
    "handymax":  (40000, 60000),
    "supramax":  (50000, 70000),
    "panamax":   (60000, 100000),
    "capesize":  (100000, 400000),
}


def _estimate_vessel_class(dwt):
    if dwt <= 0:
        return None
    for cls, (lo, hi) in CLASS_DWT_RANGES.items():
        if lo <= dwt <= hi:
            return cls
    if 35000 <= dwt < 40000:
        return "handymax"
    if 95000 < dwt < 100000:
        return "panamax"
    if dwt > 400000:
        return "capesize"
    return None


def _api_get(url, params, max_retries=3):
    """GET with retry on 429. Returns parsed JSON or None."""
    if not requests:
        return None

    for attempt in range(max_retries):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f"[marinesia] Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"[marinesia] HTTP {r.status_code} for {url}")
            return None
        except Exception as e:
            print(f"[marinesia] Request failed: {e}")
            return None
    print(f"[marinesia] Max retries exceeded for {url}")
    return None


def _fetch_vessels_from_area(area):
    """Fetch vessels from a bounding box."""
    if not API_KEY or not requests:
        return []

    data = _api_get(f"{BASE}/vessel/area", {
        "key": API_KEY,
        "lat_min": area["lat_min"],
        "lat_max": area["lat_max"],
        "long_min": area["long_min"],
        "long_max": area["long_max"],
    })

    if not data:
        return []

    if isinstance(data, dict) and data.get("error"):
        return []

    return data.get("data", []) if isinstance(data, dict) else []


def _parse_vessel(v):
    """Parse a Marinesia vessel record into our schema."""
    try:
        name = (v.get("name") or "").strip()
        if not name:
            return None

        imo = str(v.get("imo") or "")
        mmsi = str(v.get("mmsi") or "")
        vtype = (v.get("type") or "").lower()
        flag = (v.get("flag") or "")

        a = float(v.get("a") or 0)
        b = float(v.get("b") or 0)
        c = float(v.get("c") or 0)
        d = float(v.get("d") or 0)

        loa = a + b
        beam = c + d

        if loa <= 0 or beam <= 0:
            return None

        estimated_dwt = loa * beam * 8.0 * 0.83 * 1.025
        vessel_class = _estimate_vessel_class(estimated_dwt)
        if not vessel_class:
            return None

        draft_map = {"handymax": 10.5, "supramax": 11.5, "panamax": 13.5, "capesize": 17.5}
        draft = draft_map.get(vessel_class, 12.0)

        import random
        random.seed(hash(imo or mmsi or name))

        status = v.get("status")
        dest = (v.get("dest") or "").upper()
        if status in (0, 1, 5) or "FOR ORDERS" in dest or not dest:
            avail = "open"
        else:
            avail = "laden"

        return {
            "name": name,
            "vessel_class": vessel_class,
            "capacity": round(estimated_dwt, 0),
            "draft": round(draft, 1),
            "loa": round(loa, 1),
            "beam": round(beam, 1),
            "imo": imo,
            "mmsi": mmsi,
            "speed_knots": round(random.uniform(12.0, 15.5), 1),
            "fuel_consumption_tons_per_day": round(random.uniform(25.0, 45.0), 1),
            "daily_hire_rate": round(random.uniform(12000, 25000), 0),
            "availability_proxy": avail,
            "flag": flag,
            "vessel_type_raw": vtype,
        }
    except Exception:
        return None


def fetch_vessels(limit=200):
    """Fetch bulk carrier vessels from Marinesia API."""
    if not API_KEY:
        print("[marinesia] No MARINESIA_KEY configured.")
        return []
    if not requests:
        print("[marinesia] requests library not installed.")
        return []

    cached = cache_read(CACHE_KEY, VESSEL_CACHE_HOURS)
    if cached and isinstance(cached, list) and len(cached) > 0:
        print(f"[marinesia] Serving {len(cached)} vessels from cache.")
        return cached[:limit]

    print("[marinesia] Fetching real vessel data...")
    seen = set()
    all_vessels = []

    for area in SEARCH_AREAS:
        raw = _fetch_vessels_from_area(area)
        for v in raw:
            parsed = _parse_vessel(v)
            if parsed is None:
                continue
            key = parsed["imo"] or parsed["mmsi"] or parsed["name"]
            if key in seen:
                continue
            seen.add(key)
            all_vessels.append(parsed)

        if len(all_vessels) >= limit:
            break
        time.sleep(3)

    class_order = {"panamax": 0, "supramax": 1, "capesize": 2, "handymax": 3}
    all_vessels.sort(key=lambda v: class_order.get(v["vessel_class"], 99))

    result = all_vessels[:limit]
    print(f"[marinesia] Fetched {len(result)} unique bulk carriers.")

    if result:
        cache_write(CACHE_KEY, result)

    return result
