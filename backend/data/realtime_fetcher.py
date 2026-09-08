"""Unified real-time data fetcher for all analytical endpoints.

Fetches fresh data from external APIs and returns DataFrames in the same
schemas as the DB loaders. Falls back to DB if APIs fail.
"""

import pandas as pd
from datetime import date, timedelta
from sqlalchemy.orm import Session

from data.connectors.freight_stooq import fetch_bdi_daily, to_route_rates
from data.connectors.commodities_fred import fetch_commodities
from data.connectors.bunker_eia import fetch_bunker_trend, BASE_VLSFO, BASE_MGO, PORT_PREMIUM, PORTS
from data.connectors.ais_worker import get_live_port_metrics, get_live_vessel_updates


def fetch_freight_realtime(db: Session, route: str = None, vessel_class: str = None,
                           days: int = 120) -> pd.DataFrame:
    """Fetch fresh freight rates from yfinance BDRY, merge with DB history."""
    bdi_df = fetch_bdi_daily(days=days)
    if not bdi_df.empty:
        realtime_df = to_route_rates(bdi_df)
        if not realtime_df.empty:
            realtime_df["date"] = pd.to_datetime(realtime_df["date"])
            query = "SELECT * FROM freight_rates WHERE source = 'synthetic'"
            params = {}
            if route:
                query += " AND route = :route"
                params["route"] = route
            if vessel_class:
                query += " AND vessel_class = :vessel_class"
                params["vessel_class"] = vessel_class
            query += " ORDER BY date"
            try:
                from database.postgres import engine
                from sqlalchemy import text
                hist_df = pd.read_sql(text(query), engine, params=params)
                hist_df["date"] = pd.to_datetime(hist_df["date"])
            except Exception:
                hist_df = pd.DataFrame()

            if not hist_df.empty:
                combined = pd.concat([hist_df, realtime_df], ignore_index=True)
                combined = combined.drop_duplicates(subset=["date", "route", "vessel_class"], keep="last")
                combined = combined.sort_values("date").reset_index(drop=True)
            else:
                combined = realtime_df

            if route:
                combined = combined[combined["route"] == route]
            if vessel_class:
                combined = combined[combined["vessel_class"] == vessel_class]

            return combined

    from data.preprocessing import load_freight_rates
    return load_freight_rates(db, route=route, vessel_class=vessel_class)


def fetch_commodity_realtime(db: Session) -> pd.DataFrame:
    """Fetch fresh commodity prices from FRED, merge with DB history."""
    realtime_df = fetch_commodities()
    if not realtime_df.empty:
        realtime_df["date"] = pd.to_datetime(realtime_df["date"])
        try:
            from database.postgres import engine
            from sqlalchemy import text
            hist_df = pd.read_sql(
                text("SELECT * FROM commodity_prices ORDER BY date"), engine
            )
            hist_df["date"] = pd.to_datetime(hist_df["date"])
        except Exception:
            hist_df = pd.DataFrame()

        if not hist_df.empty:
            combined = pd.concat([hist_df, realtime_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
        else:
            combined = realtime_df
        return combined

    from data.preprocessing import load_commodity_prices
    return load_commodity_prices(db)


def fetch_bunker_realtime(db: Session, port: str = None) -> pd.DataFrame:
    """Fetch fresh bunker prices from EIA, merge with DB history."""
    baseline = None
    try:
        from database.postgres import engine
        from sqlalchemy import text
        baseline = pd.read_sql(
            text("SELECT vlsfo_price, mgo_price FROM bunker_prices ORDER BY date DESC LIMIT 50"),
            engine
        )
    except Exception:
        pass

    realtime_df = fetch_bunker_trend(baseline)
    if not realtime_df.empty:
        realtime_df["date"] = pd.to_datetime(realtime_df["date"])
        try:
            from database.postgres import engine
            from sqlalchemy import text
            hist_df = pd.read_sql(
                text("SELECT * FROM bunker_prices ORDER BY date"), engine
            )
            hist_df["date"] = pd.to_datetime(hist_df["date"])
        except Exception:
            hist_df = pd.DataFrame()

        if not hist_df.empty:
            combined = pd.concat([hist_df, realtime_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "port"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
        else:
            combined = realtime_df

        if port:
            combined = combined[combined["port"] == port]
        return combined

    from data.preprocessing import load_bunker_prices
    return load_bunker_prices(db, port=port)


def fetch_congestion_realtime(db: Session, port_name: str = None) -> pd.DataFrame:
    """Fetch live congestion from AIS worker, merge with DB history."""
    live_metrics = get_live_port_metrics()
    live_rows = []
    for port_name_key, m in live_metrics.items():
        live_rows.append({
            "date": pd.to_datetime(m["date"]),
            "port_name": port_name_key,
            "congestion_index": m["congestion_index"],
            "expected_delay_hours": m["expected_delay_hours"],
            "vessels_waiting": m["vessels_waiting"],
            "source": "live/aisstream",
        })

    if live_rows:
        live_df = pd.DataFrame(live_rows)
        try:
            from database.postgres import engine
            from sqlalchemy import text
            hist_df = pd.read_sql(
                text("""
                    SELECT pc.*, p.name as port_name
                    FROM port_congestion pc
                    JOIN ports p ON pc.port_id = p.port_id
                    ORDER BY pc.date
                """), engine
            )
            hist_df["date"] = pd.to_datetime(hist_df["date"])
        except Exception:
            hist_df = pd.DataFrame()

        if not hist_df.empty:
            combined = pd.concat([hist_df, live_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "port_name"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
        else:
            combined = live_df

        if port_name:
            combined = combined[combined["port_name"] == port_name]
        return combined

    from data.preprocessing import load_congestion
    return load_congestion(db, port_name=port_name)


def fetch_vessels_realtime(db: Session, vessel_class: str = None) -> pd.DataFrame:
    """Fetch live vessel positions from AIS worker, merge with DB."""
    from data.preprocessing import load_vessels
    vessels_df = load_vessels(db, vessel_class=vessel_class)

    live_updates = get_live_vessel_updates()
    if live_updates and not vessels_df.empty:
        updates_df = pd.DataFrame(live_updates)
        if "mmsi" in updates_df.columns and "mmsi" in vessels_df.columns:
            vessels_df = vessels_df.merge(
                updates_df[["mmsi", "lat", "lon", "sog", "last_ais_at", "destination_raw", "eta_raw"]],
                on="mmsi", how="left", suffixes=("", "_live")
            )
            for col in ["lat", "lon", "sog", "last_ais_at", "destination_raw", "eta_raw"]:
                live_col = f"{col}_live"
                if live_col in vessels_df.columns:
                    vessels_df[col] = vessels_df[live_col].combine_first(vessels_df.get(col))
                    vessels_df = vessels_df.drop(columns=[live_col])

    return vessels_df


def fetch_all_realtime(db: Session, route: str = None, vessel_class: str = None) -> dict:
    """Fetch all datasets fresh from APIs in one call."""
    return {
        "freight": fetch_freight_realtime(db, route=route, vessel_class=vessel_class),
        "commodities": fetch_commodity_realtime(db),
        "bunker": fetch_bunker_realtime(db),
        "congestion": fetch_congestion_realtime(db),
        "vessels": fetch_vessels_realtime(db, vessel_class=vessel_class),
        "ports": _fetch_ports(db),
        "contracts": _fetch_contracts(db),
    }


def _fetch_ports(db: Session) -> pd.DataFrame:
    from data.preprocessing import load_ports
    return load_ports(db)


def _fetch_contracts(db: Session) -> pd.DataFrame:
    from data.preprocessing import load_contracts
    return load_contracts(db)
