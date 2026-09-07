"""Bunker: EIA free API trend (free key) applied to last DB Singapore baseline.

No $0 API publishes Paradip/Dhamra VLSFO directly, so this reuses the
existing per-port premium approach: fetch the real fuel-oil trend from EIA,
then scale stored port prices. Output matches bunker_prices schema.
Ports here must match ingestion.generate_ports() names.
"""

import os
import pandas as pd

from .base import http_get

PORTS = ["Paradip", "Dhamra", "Gangavaram", "Vizag", "Mundra"]
PORT_PREMIUM = {"Paradip": 0, "Dhamra": 5, "Gangavaram": 8, "Vizag": 3, "Mundra": 12}
BASE_VLSFO = float(os.getenv("BUNKER_BASE_VLSFO", "590"))
BASE_MGO = float(os.getenv("BUNKER_BASE_MGO", "760"))


def _fetch_eia_residual_factor() -> float:
    """Returns ratio vs BASE (1.0 = no change). 1.0 when key missing/failure."""
    api_key = os.getenv("EIA_KEY", "").strip()
    if not api_key:
        return 1.0
    # Weekly retail/residual series; keep single generic call to stay in free quota.
    text, _ = http_get(
        "https://api.eia.gov/v2/petroleum/pri/spt/data/",
        params={
            "api_key": api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "facets[product][]": "EPRD",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 8,
        },
        timeout=25,
        cache_key="eia_residual",
        cache_hours=20,
    )
    if not text:
        return 1.0
    try:
        import json as _json
        payload = _json.loads(text)
        series = payload.get("response", {}).get("data", []) or []
        vals = [float(r.get("value")) for r in series if r.get("value") not in (None, "")]
        if len(vals) < 2:
            return 1.0
        # 4-wk momentum, clamped to avoid spikes from sparse EIA weeks
        recent = sum(vals[:2]) / 2
        older = sum(vals[-2:]) / 2
        if older <= 0:
            return 1.0
        return max(0.85, min(1.15, recent / older))
    except Exception as e:
        print(f"[eia] parse failed, using 1.0: {e}")
        return 1.0


def fetch_bunker_trend(baseline: pd.DataFrame | None = None) -> pd.DataFrame:
    """Builds today's per-port rows. baseline optionally carries last DB means."""
    from datetime import date as _date
    # Fail soft with empty frame when no key — sync_service then keeps DB values.
    if not os.getenv("EIA_KEY", "").strip():
        return pd.DataFrame()
    factor = _fetch_eia_residual_factor()
    vlsfo = BASE_VLSFO * factor
    mgo = BASE_MGO * factor
    if baseline is not None and not baseline.empty:
        try:
            # Anchor to reality: scale last stored means by EIA factor
            last_v = float(baseline["vlsfo_price"].dropna().iloc[-1])
            last_m = float(baseline["mgo_price"].dropna().iloc[-1])
            if last_v > 0:
                vlsfo = last_v * factor
            if last_m > 0:
                mgo = last_m * factor
        except Exception:
            pass
    today = _date.today()
    rows = [{
        "date": today,
        "port": p,
        "vlsfo_price": round(vlsfo + PORT_PREMIUM[p], 2),
        "mgo_price": round(mgo + PORT_PREMIUM[p], 2),
        "source": "live/eia-trend",
    } for p in PORTS]
    return pd.DataFrame(rows)
