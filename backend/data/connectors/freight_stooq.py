"""Freight: Stooq BDI daily (free-registration key) → route $/MT proxy.

No free API publishes Australia-Paradip Panamax $/t directly, so this keeps
the existing route_premiums/base_rates scaling from ingestion.py and drives
it with the real Baltic Dry Index close. Honest proxy, labelled live/stooq.
"""

import os
from datetime import date, timedelta
import pandas as pd

from .base import http_get, parse_csv_rows

ROUTES = [
    "Australia-Paradip", "Australia-Dhamra", "Australia-Gangavaram",
    "Australia-Vizag", "South Africa-Paradip", "Indonesia-Paradip",
    "Australia-Mundra", "Indonesia-Mundra",
]
VESSEL_CLASSES = ["panamax", "supramax", "handymax", "capesize"]
BASE_RATES = {"panamax": 18.0, "supramax": 20.0, "handymax": 22.0, "capesize": 15.0}
ROUTE_PREMIUMS = {
    "Australia-Paradip": 0, "Australia-Dhamra": 1.2, "Australia-Gangavaram": 0.8,
    "Australia-Vizag": 1.0, "South Africa-Paradip": 3.5, "Indonesia-Paradip": -2.0,
    "Australia-Mundra": 2.5, "Indonesia-Mundra": -1.0,
}
# Calibrated once: BDI ~1500 ≈ panamax Australia-Paradip ~$18-22/t.
BDI_REFERENCE = float(os.getenv("BDI_REFERENCE", "1500"))
BDI_SENSITIVITY = float(os.getenv("BDI_SENSITIVITY", "0.006"))  # $/t per BDI point


def fetch_bdi_daily(days: int = 120) -> pd.DataFrame:
    """Returns DataFrame(date, bdi). Empty DF when key missing/quota hit."""
    api_key = os.getenv("STOOQ_KEY", "").strip()
    if not api_key:
        return pd.DataFrame()
    end = date.today()
    start = end - timedelta(days=days)
    d1 = start.strftime("%Y%m%d")
    d2 = end.strftime("%Y%m%d")
    text, _ = http_get(
        "https://stooq.com/q/d/l/",
        params={"s": "bdi", "i": "d", "d1": d1, "d2": d2, "apikey": api_key},
        timeout=25,
        cache_key="stooq_bdi_daily",
        cache_hours=20,  # respect daily quota: at most ~1 live call/day
    )
    if not text or "Exceeded the daily hits limit" in text:
        return pd.DataFrame()
    rows = parse_csv_rows(text)
    records = []
    for r in rows:
        try:
            close = float(r.get("Close") or 0)
            if close <= 0:
                continue
            records.append({"date": pd.to_datetime(r["Date"]).date(), "bdi": round(close, 1)})
        except Exception:
            continue
    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


def to_route_rates(bdi_df: pd.DataFrame) -> pd.DataFrame:
    """Scale BDI closes to per-route, per-class $/t rows (same schema as synthetic)."""
    if bdi_df is None or bdi_df.empty:
        return pd.DataFrame()
    records = []
    for _, row in bdi_df.iterrows():
        delta = (float(row["bdi"]) - BDI_REFERENCE) * BDI_SENSITIVITY
        for route in ROUTES:
            for vc in VESSEL_CLASSES:
                rate = max(5.0, BASE_RATES[vc] + ROUTE_PREMIUMS[route] + delta)
                records.append({
                    "date": row["date"],
                    "route": route,
                    "vessel_class": vc,
                    "rate_usd_per_ton": round(rate, 2),
                    "source": "live/stooq-bdi",
                })
    return pd.DataFrame(records)
