"""Freight: BDRY ETF via yfinance (free, no API key) → route $/MT proxy.

BDRY tracks dry bulk shipping rates (correlates with BDI). No free API publishes
Australia-Paradip Panamax $/t directly, so this keeps the existing
route_premiums/base_rates scaling from ingestion.py and drives it with BDRY
close as a BDI proxy. Labelled live/yfinance.
"""

import pandas as pd
from datetime import date, timedelta

from .base import cache_read, cache_write

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
# BDRY ETF ~$15 correlates to BDI ~1500 (scale factor ~100x).
BDI_SENSITIVITY = 0.006  # $/t per BDI-equivalent point

BDI_TICKER = "BDRY"
BDI_REFERENCE = 1500.0  # reference BDI level for calibration
BDRY_TO_BDI_SCALE = 100.0  # BDRY * 100 ≈ BDI equivalent
CACHE_KEY = "yfinance_bdi_daily"
CACHE_HOURS = 6


def fetch_bdi_daily(days: int = 120) -> pd.DataFrame:
    """Returns DataFrame(date, bdi). bdi column is BDI-equivalent scaled from BDRY. Empty DF on failure."""
    hit = cache_read(CACHE_KEY, CACHE_HOURS)
    if hit and isinstance(hit, dict) and "data" in hit:
        try:
            df = pd.DataFrame(hit["data"])
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"]).dt.date
                return df
        except Exception:
            pass

    try:
        import yfinance as yf
        end = date.today()
        start = end - timedelta(days=days)
        ticker = yf.Ticker(BDI_TICKER)
        hist = ticker.history(start=start.isoformat(), end=end.isoformat())
        if hist.empty:
            return pd.DataFrame()
        # Scale BDRY close to BDI-equivalent (BDRY ~$15 = BDI ~1500)
        bdi_equivalent = hist["Close"] * BDRY_TO_BDI_SCALE
        df = pd.DataFrame({
            "date": hist.index.date,
            "bdi": bdi_equivalent.round(1).values,
        })
        df = df[df["bdi"] > 0].sort_values("date").reset_index(drop=True)
        if not df.empty:
            cache_write(CACHE_KEY, {"data": df.to_dict(orient="records")})
        return df
    except Exception as e:
        print(f"[yfinance] BDI fetch failed: {e}")
        return pd.DataFrame()


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
                    "source": "live/yfinance-bdi",
                })
    return pd.DataFrame(records)
