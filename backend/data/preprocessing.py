import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import text
from database.postgres import engine


def load_freight_rates(db: Session, route: str = None, vessel_class: str = None,
                       start_date: str = None, end_date: str = None):
    query = "SELECT * FROM freight_rates WHERE 1=1"
    params = {}

    if route:
        query += " AND route = :route"
        params["route"] = route
    if vessel_class:
        query += " AND vessel_class = :vessel_class"
        params["vessel_class"] = vessel_class
    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date"
    df = pd.read_sql(text(query), engine, params=params)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_commodity_prices(db: Session, start_date: str = None, end_date: str = None):
    query = "SELECT * FROM commodity_prices WHERE 1=1"
    params = {}
    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date"
    df = pd.read_sql(text(query), engine, params=params)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_bunker_prices(db: Session, port: str = None, start_date: str = None, end_date: str = None):
    query = "SELECT * FROM bunker_prices WHERE 1=1"
    params = {}
    if port:
        query += " AND port = :port"
        params["port"] = port
    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date"
    df = pd.read_sql(text(query), engine, params=params)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_congestion(db: Session, port_name: str = None, start_date: str = None, end_date: str = None):
    query = """
        SELECT pc.*, p.name as port_name
        FROM port_congestion pc
        JOIN ports p ON pc.port_id = p.port_id
        WHERE 1=1
    """
    params = {}
    if port_name:
        query += " AND p.name = :port_name"
        params["port_name"] = port_name
    if start_date:
        query += " AND pc.date >= :start_date"
        params["start_date"] = start_date
    if end_date:
        query += " AND pc.date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY pc.date"
    df = pd.read_sql(text(query), engine, params=params)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_vessels(db: Session, vessel_class: str = None):
    query = "SELECT * FROM vessels WHERE 1=1"
    params = {}
    if vessel_class:
        query += " AND vessel_class = :vessel_class"
        params["vessel_class"] = vessel_class
    return pd.read_sql(text(query), engine, params=params)


def load_ports(db: Session):
    return pd.read_sql(text("SELECT * FROM ports"), engine)


def load_contracts(db: Session):
    return pd.read_sql(text("SELECT * FROM contracts"), engine)


def load_cargo_requirements(db: Session, cargo_id: int = None):
    query = "SELECT * FROM cargo_requirements WHERE 1=1"
    params = {}
    if cargo_id:
        query += " AND cargo_id = :cargo_id"
        params["cargo_id"] = cargo_id
    return pd.read_sql(text(query), engine, params=params)


def create_features(freight_df: pd.DataFrame, commodity_df: pd.DataFrame = None,
                    bunker_df: pd.DataFrame = None):
    df = freight_df.copy()
    df = df.sort_values("date").reset_index(drop=True)

    df["month"] = df["date"].dt.month
    df["week"] = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_week"] = df["date"].dt.dayofweek
    df["quarter"] = df["date"].dt.quarter
    df["year"] = df["date"].dt.year

    df["day_of_year"] = df["date"].dt.dayofyear
    df["sin_day"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["cos_day"] = np.cos(2 * np.pi * df["day_of_year"] / 365)
    df["sin_month"] = np.sin(2 * np.pi * df["month"] / 12)
    df["cos_month"] = np.cos(2 * np.pi * df["month"] / 12)

    for window in [7, 14, 30, 60, 90]:
        df[f"rolling_mean_{window}"] = df.groupby("route")["rate_usd_per_ton"].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )
        df[f"rolling_std_{window}"] = df.groupby("route")["rate_usd_per_ton"].transform(
            lambda x: x.rolling(window, min_periods=1).std()
        )

    df["momentum_7"] = df.groupby("route")["rate_usd_per_ton"].transform(
        lambda x: x.pct_change(7)
    )
    df["momentum_30"] = df.groupby("route")["rate_usd_per_ton"].transform(
        lambda x: x.pct_change(30)
    )

    df["volatility_30"] = df.groupby("route")["rate_usd_per_ton"].transform(
        lambda x: x.rolling(30, min_periods=7).std() / x.rolling(30, min_periods=7).mean()
    )

    df["lag_1"] = df.groupby("route")["rate_usd_per_ton"].shift(1)
    df["lag_7"] = df.groupby("route")["rate_usd_per_ton"].shift(7)
    df["lag_30"] = df.groupby("route")["rate_usd_per_ton"].shift(30)

    if commodity_df is not None and not commodity_df.empty:
        commodity_df = commodity_df[["date", "coal_price", "steel_price", "iron_ore_price"]].copy()
        commodity_df["date"] = pd.to_datetime(commodity_df["date"])
        df = df.merge(commodity_df, on="date", how="left")
        for col in ["coal_price", "steel_price", "iron_ore_price"]:
            df[col] = df[col].ffill()

    if bunker_df is not None and not bunker_df.empty:
        bunker_avg = bunker_df.groupby("date")["vlsfo_price"].mean().reset_index()
        bunker_avg.columns = ["date", "avg_bunker_price"]
        bunker_avg["date"] = pd.to_datetime(bunker_avg["date"])
        df = df.merge(bunker_avg, on="date", how="left")
        df["avg_bunker_price"] = df["avg_bunker_price"].ffill()

    df = df.dropna(subset=["rate_usd_per_ton"])

    return df
