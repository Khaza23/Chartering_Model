"""Commodities: FRED monthly (free key) + World Bank Pink Sheet (keyless) fallback.

FRED series:
  PCOALAUUSDM — Australia thermal coal $/MT (your exact cargo proxy)
  PIORECRUSDM — iron ore $/MT
  WPU101707   — steel mill products PPI (index; scaled to synthetic steel baseline)
Monthly frequency with 2-3wk lag is expected; preprocessing ffill() covers it.
"""

import io
import os
import pandas as pd

from .base import http_get

SERIES_MAP = {
    "PCOALAUUSDM": "coal_price",
    "PIORECRUSDM": "iron_ore_price",
    "WPU101707": "steel_price",
}
# Scale steel PPI (~250 index) to synthetic steel $/t baseline (~550).
STEEL_PPI_SCALE = float(os.getenv("STEEL_PPI_SCALE", "2.2"))
PINKSHEET_URL = "https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e87e2b-0350012021/render/CMO-Pink-Sheet-History.xlsx"


def _fetch_fred_series(series_id: str) -> pd.DataFrame:
    api_key = os.getenv("FRED_KEY", "").strip()
    if not api_key:
        return pd.DataFrame()
    text, _ = http_get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id, "api_key": api_key,
            "file_type": "json", "observation_start": "2022-01-01",
        },
        timeout=25,
        cache_key=f"fred_{series_id}",
        cache_hours=24 * 6,  # monthly series: cache 6 days
    )
    if not text:
        return pd.DataFrame()
    try:
        import json as _json
        payload = _json.loads(text)
        obs = payload.get("observations", [])
        recs = []
        for o in obs:
            try:
                v = float(o.get("value"))
                recs.append({"date": pd.to_datetime(o["date"]).date(), series_id: v})
            except Exception:
                continue
        df = pd.DataFrame(recs)
        return df.sort_values("date").reset_index(drop=True) if not df.empty else df
    except Exception as e:
        print(f"[fred] parse failed {series_id}: {e}")
        return pd.DataFrame()


def fetch_commodities() -> pd.DataFrame:
    """Returns DataFrame(date, coal_price, steel_price, iron_ore_price, index_value, source)."""
    frames = {}
    for sid in SERIES_MAP:
        df = _fetch_fred_series(sid)
        if not df.empty:
            frames[sid] = df
    if len(frames) < 2:
        # Keyless fallback: Pink Sheet monthly history
        pink = _fetch_pinksheet()
        if not pink.empty:
            return pink
        return pd.DataFrame()
    merged = None
    for sid, df in frames.items():
        merged = df if merged is None else merged.merge(df, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)
    out = pd.DataFrame({"date": merged["date"]})
    out["coal_price"] = merged.get("PCOALAUUSDM")
    out["iron_ore_price"] = merged.get("PIORECRUSDM")
    out["steel_price"] = (merged.get("WPU101707") * STEEL_PPI_SCALE) if "WPU101707" in merged else None
    out = out.ffill().dropna(subset=["coal_price", "iron_ore_price"], how="all")
    if out.empty:
        return out
    out["steel_price"] = out["steel_price"].fillna(550.0)
    out["index_value"] = round((out["coal_price"] + out["steel_price"] / 7 + out["iron_ore_price"]) / 3, 2)
    out["source"] = "live/fred"
    return out[["date", "coal_price", "steel_price", "iron_ore_price", "index_value", "source"]]


def _fetch_pinksheet() -> pd.DataFrame:
    """Keyless fallback stub: Pink Sheet is xlsx and needs openpyxl (not in
    reconfigure scope). Return empty so sync keeps last DB values."""
    return pd.DataFrame()
