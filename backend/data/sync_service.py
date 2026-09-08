"""Idempotent $0 live-sync: fetch -> normalize -> upsert -> log to sync_runs.

Reconfigure-only: never drops tables, never breaks on missing keys.
All failures are logged with status=failed/skipped and old DB rows kept.
"""

import os
import traceback
from datetime import datetime, date
from typing import Dict

import pandas as pd

import sys as _sys
import os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

from database.postgres import SessionLocal, engine
from database.models_db import SyncRun

DATASETS = ["freight", "bunker", "commodities", "congestion"]


def _log_run(dataset: str, status: str, rows: int = 0, error: str | None = None):
    try:
        db = SessionLocal()
        db.add(SyncRun(
            dataset=dataset, finished_at=datetime.utcnow(),
            status=status, rows_upserted=int(rows), error=(error or "")[:2000] if error else None,
        ))
        db.commit()
        db.close()
    except Exception as e:
        print(f"[sync] log failed: {e}")


def sync_freight() -> int:
    """BDI via yfinance -> route $/t upsert. Returns rows upserted."""
    try:
        from data.connectors.freight_stooq import fetch_bdi_daily, to_route_rates
        bdi = fetch_bdi_daily(days=120)
        if bdi.empty:
            _log_run("freight", "skipped", 0, "BDI fetch failed; kept DB values")
            return 0
        df = to_route_rates(bdi)
        if df.empty:
            _log_run("freight", "skipped", 0, "Empty route-rate frame")
            return 0
        # Only upsert dates not already covered by live source to avoid rewriting history
        existing = pd.read_sql("SELECT date, route, vessel_class FROM freight_rates WHERE source LIKE 'live/%'", engine)
        if not existing.empty:
            existing["date"] = pd.to_datetime(existing["date"]).dt.date
            df["date"] = pd.to_datetime(df["date"]).dt.date
            merged = df.merge(existing, on=["date", "route", "vessel_class"], how="left", indicator=True)
            df = merged[merged["_merge"] == "left_only"].drop(columns=["_merge"])
        if df.empty:
            _log_run("freight", "success", 0, None)
            return 0
        df["fetched_at"] = datetime.utcnow()
        df.to_sql("freight_rates", engine, if_exists="append", index=False, chunksize=2000)
        _log_run("freight", "success", len(df), None)
        return len(df)
    except Exception as e:
        _log_run("freight", "failed", 0, f"{e}\n{traceback.format_exc()[-800:]}")
        return 0


def sync_commodities() -> int:
    try:
        from data.connectors.commodities_fred import fetch_commodities
        df = fetch_commodities()
        if df.empty:
            _log_run("commodities", "skipped", 0, "No FRED_KEY or fetch failed; kept DB values")
            return 0
        df["date"] = pd.to_datetime(df["date"]).dt.date
        existing_dates = set(pd.read_sql("SELECT date FROM commodity_prices", engine)["date"].astype(str).tolist()) \
            if True else set()
        # Normalize existing to date strings for comparison
        try:
            ex = pd.read_sql("SELECT date FROM commodity_prices", engine)
            existing_dates = set(pd.to_datetime(ex["date"]).dt.date.astype(str).tolist())
        except Exception:
            existing_dates = set()
        df = df[~df["date"].astype(str).isin(existing_dates)]
        if df.empty:
            _log_run("commodities", "success", 0, None)
            return 0
        df["fetched_at"] = datetime.utcnow()
        df.to_sql("commodity_prices", engine, if_exists="append", index=False)
        _log_run("commodities", "success", len(df), None)
        return len(df)
    except Exception as e:
        _log_run("commodities", "failed", 0, f"{e}\n{traceback.format_exc()[-800:]}")
        return 0


def sync_bunker() -> int:
    try:
        from data.connectors.bunker_eia import fetch_bunker_trend
        try:
            baseline = pd.read_sql("SELECT vlsfo_price, mgo_price FROM bunker_prices ORDER BY date DESC LIMIT 50", engine)
        except Exception:
            baseline = None
        df = fetch_bunker_trend(baseline)
        if df.empty:
            _log_run("bunker", "skipped", 0, "Bunker fetch empty")
            return 0
        df["date"] = pd.to_datetime(df["date"]).dt.date
        try:
            ex = pd.read_sql("SELECT date, port FROM bunker_prices WHERE date = CURRENT_DATE", engine)
            if not ex.empty:
                _log_run("bunker", "success", 0, "Today already synced")
                return 0
        except Exception:
            pass
        df["fetched_at"] = datetime.utcnow()
        df.to_sql("bunker_prices", engine, if_exists="append", index=False)
        _log_run("bunker", "success", len(df), None)
        return len(df)
    except Exception as e:
        _log_run("bunker", "failed", 0, f"{e}\n{traceback.format_exc()[-800:]}")
        return 0


def sync_congestion_from_live_metrics(metrics: Dict[str, dict]) -> int:
    """Upsert today's AIS-derived congestion snapshot. Called by scheduler/worker."""
    if not metrics:
        return 0
    try:
        ports = pd.read_sql("SELECT port_id, name FROM ports", engine)
        name_to_id = {r["name"]: int(r["port_id"]) for _, r in ports.iterrows()}
        rows = []
        today = date.today()
        for port_name, m in metrics.items():
            pid = name_to_id.get(port_name)
            if not pid:
                continue
            rows.append({
                "date": today, "port_id": pid,
                "congestion_index": float(m.get("congestion_index", 30)),
                "expected_delay_hours": float(m.get("expected_delay_hours", 12)),
                "vessels_waiting": int(m.get("vessels_waiting", 0)),
                "source": "live/aisstream", "fetched_at": datetime.utcnow(),
            })
        if not rows:
            return 0
        df = pd.DataFrame(rows)
        # Replace today's live rows to keep waiting counts fresh (idempotent)
        from sqlalchemy import text as _text
        with engine.begin() as conn:
            conn.execute(_text("DELETE FROM port_congestion WHERE date = :d AND source LIKE 'live/%'"), {"d": today})
        df.to_sql("port_congestion", engine, if_exists="append", index=False)
        _log_run("congestion", "success", len(df), None)
        return len(df)
    except Exception as e:
        _log_run("congestion", "failed", 0, f"{e}\n{traceback.format_exc()[-800:]}")
        return 0


def sync_vessel_positions(updates: list) -> int:
    """Update Vessel live AIS fields by mmsi or name. Never touches static specs."""
    if not updates:
        return 0
    try:
        from database.models_db import Vessel
        db = SessionLocal()
        count = 0
        for u in updates:
            mmsi = str(u.get("mmsi") or "")
            name = u.get("name") or ""
            vessel = None
            if mmsi:
                vessel = db.query(Vessel).filter(Vessel.mmsi == mmsi).first()
            if vessel is None and name:
                vessel = db.query(Vessel).filter(Vessel.name == name).first()
            if vessel is None:
                continue
            if u.get("lat") is not None:
                vessel.last_lat = float(u["lat"])
            if u.get("lon") is not None:
                vessel.last_lon = float(u["lon"])
            if u.get("last_ais_at") is not None:
                vessel.last_ais_at = u["last_ais_at"]
            if u.get("destination_raw"):
                vessel.destination_raw = str(u["destination_raw"])[:100]
            if u.get("eta_raw"):
                vessel.eta_raw = str(u["eta_raw"])[:100]
            dest = (u.get("destination_raw") or "").upper()
            if any(p in dest for p in ["PARADIP", "DHAMRA", "VIZAG", "GANGAVARAM", "MUNDRA"]):
                vessel.availability_proxy = "open"
            elif dest:
                vessel.availability_proxy = "laden"
            count += 1
        db.commit()
        db.close()
        return count
    except Exception as e:
        print(f"[sync] vessel update failed: {e}")
        return 0


def sync_dataset(name: str) -> Dict:
    name = (name or "").lower()
    if name == "freight":
        rows = sync_freight()
    elif name == "commodities":
        rows = sync_commodities()
    elif name == "bunker":
        rows = sync_bunker()
    elif name == "congestion":
        try:
            from data.connectors.ais_worker import get_live_port_metrics, get_live_vessel_updates
            rows = sync_congestion_from_live_metrics(get_live_port_metrics())
            sync_vessel_positions(get_live_vessel_updates())
        except Exception:
            rows = 0
            _log_run("congestion", "skipped", 0, "AIS worker has no data yet")
    else:
        return {"dataset": name, "error": f"Unknown dataset. Use one of {DATASETS}"}
    return {"dataset": name, "rows_upserted": rows}


def sync_all() -> Dict:
    results = {}
    for ds in DATASETS:
        try:
            results[ds] = sync_dataset(ds)
        except Exception as e:
            results[ds] = {"dataset": ds, "error": str(e)}
    return results
