import pandas as pd
import numpy as np
from datetime import date, timedelta
from sqlalchemy.orm import Session
from database.postgres import engine, SessionLocal, init_db
from database.models_db import (
    FreightRate, CommodityPrice, BunkerPrice, Port, Vessel,
    PortCongestion, CargoRequirement, Contract
)


def generate_synthetic_freight_rates(start_date=date(2023, 1, 1), end_date=date(2025, 12, 31)):
    routes = [
        "Australia-Paradip", "Australia-Dhamra", "Australia-Gangavaram",
        "Australia-Vizag", "South Africa-Paradip", "Indonesia-Paradip",
        "Australia-Mundra", "Indonesia-Mundra"
    ]
    vessel_classes = ["panamax", "supramax", "handymax", "capesize"]

    base_rates = {
        "panamax": 18.0, "supramax": 20.0, "handymax": 22.0, "capesize": 15.0
    }
    route_premiums = {
        "Australia-Paradip": 0, "Australia-Dhamra": 1.2, "Australia-Gangavaram": 0.8,
        "Australia-Vizag": 1.0, "South Africa-Paradip": 3.5, "Indonesia-Paradip": -2.0,
        "Australia-Mundra": 2.5, "Indonesia-Mundra": -1.0
    }

    np.random.seed(42)
    records = []
    current = start_date
    trend = 0.001

    while current <= end_date:
        day_of_year = current.timetuple().tm_yday
        seasonal = 2.5 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
        noise = np.random.normal(0, 1.2)
        cumulative_trend = trend * (current - start_date).days

        for route in routes:
            for vc in vessel_classes:
                rate = (
                    base_rates[vc]
                    + route_premiums[route]
                    + seasonal
                    + cumulative_trend
                    + noise
                    + np.random.normal(0, 0.5)
                )
                rate = max(rate, 5.0)
                records.append({
                    "date": current,
                    "route": route,
                    "vessel_class": vc,
                    "rate_usd_per_ton": round(rate, 2),
                    "source": "synthetic"
                })
        current += timedelta(days=1)

    return pd.DataFrame(records)


def generate_synthetic_commodity_prices(start_date=date(2023, 1, 1), end_date=date(2025, 12, 31)):
    np.random.seed(43)
    records = []
    current = start_date

    coal = 75.0
    steel = 550.0
    iron_ore = 90.0

    while current <= end_date:
        coal += np.random.normal(0.05, 1.5)
        steel += np.random.normal(0.3, 5.0)
        iron_ore += np.random.normal(0.1, 2.0)

        coal = max(coal, 30.0)
        steel = max(steel, 300.0)
        iron_ore = max(iron_ore, 40.0)

        records.append({
            "date": current,
            "coal_price": round(coal, 2),
            "steel_price": round(steel, 2),
            "iron_ore_price": round(iron_ore, 2),
            "index_value": round((coal + steel / 7 + iron_ore) / 3, 2)
        })
        current += timedelta(days=1)

    return pd.DataFrame(records)


def generate_synthetic_bunker_prices(start_date=date(2023, 1, 1), end_date=date(2025, 12, 31)):
    ports = ["Paradip", "Dhamra", "Gangavaram", "Vizag", "Mundra"]
    np.random.seed(44)
    records = []
    current = start_date

    vlsfo = 400.0
    mgo = 500.0

    while current <= end_date:
        vlsfo += np.random.normal(0.2, 5.0)
        mgo += np.random.normal(0.25, 6.0)

        vlsfo = max(vlsfo, 150.0)
        mgo = max(mgo, 200.0)

        for port in ports:
            port_premium = {"Paradip": 0, "Dhamra": 5, "Gangavaram": 8, "Vizag": 3, "Mundra": 12}
            records.append({
                "date": current,
                "port": port,
                "vlsfo_price": round(vlsfo + port_premium[port], 2),
                "mgo_price": round(mgo + port_premium[port], 2)
            })
        current += timedelta(days=1)

    return pd.DataFrame(records)


def generate_ports():
    return [
        {"name": "Paradip", "country": "India", "region": "East Coast",
         "draft_limit": 17.5, "loa_limit": 290.0, "beam_limit": 45.0,
         "berth_capacity": 8, "avg_turnaround_hours": 72.0, "cargo_handling_rate": 3500.0},
        {"name": "Dhamra", "country": "India", "region": "East Coast",
         "draft_limit": 18.0, "loa_limit": 300.0, "beam_limit": 50.0,
         "berth_capacity": 6, "avg_turnaround_hours": 60.0, "cargo_handling_rate": 4000.0},
        {"name": "Gangavaram", "country": "India", "region": "East Coast",
         "draft_limit": 18.5, "loa_limit": 290.0, "beam_limit": 45.0,
         "berth_capacity": 10, "avg_turnaround_hours": 54.0, "cargo_handling_rate": 4500.0},
        {"name": "Vizag", "country": "India", "region": "East Coast",
         "draft_limit": 16.5, "loa_limit": 280.0, "beam_limit": 42.0,
         "berth_capacity": 12, "avg_turnaround_hours": 80.0, "cargo_handling_rate": 3000.0},
        {"name": "Mundra", "country": "India", "region": "West Coast",
         "draft_limit": 17.0, "loa_limit": 285.0, "beam_limit": 44.0,
         "berth_capacity": 15, "avg_turnaround_hours": 48.0, "cargo_handling_rate": 5000.0},
    ]


def generate_vessels():
    np.random.seed(45)
    vessel_specs = {
        "panamax": {"capacity_range": (70000, 85000), "draft": (13.0, 14.5),
                    "loa": (225, 235), "beam": (32.0, 32.5)},
        "supramax": {"capacity_range": (50000, 65000), "draft": (11.0, 12.5),
                     "loa": (190, 205), "beam": (28.0, 32.0)},
        "handymax": {"capacity_range": (40000, 55000), "draft": (10.0, 11.5),
                     "loa": (180, 195), "beam": (25.0, 28.0)},
        "capesize": {"capacity_range": (150000, 200000), "draft": (17.0, 18.5),
                     "loa": (280, 300), "beam": (45.0, 48.0)},
    }

    vessels = []
    names = [
        "MV Iron Star", "MV Coal Pioneer", "MV Bulk Carrier", "MV Ocean Trader",
        "MV Sea Fortune", "MV Pacific Star", "MV Indian Ocean", "MV Bay of Bengal",
        "MV Coral Sea", "MV Sunset Express", "MV Dawn Pioneer", "MV Horizon",
        "MV Nordic Wind", "MV Southern Cross", "MV Red Sea", "MV Golden Phoenix",
        "MV Blue Ocean", "MV Silver Wave", "MV Bronze Eagle", "MV Crystal Tide"
    ]

    for i, name in enumerate(names):
        vc = list(vessel_specs.keys())[i % len(vessel_specs.keys())]
        spec = vessel_specs[vc]
        avail_start = date(2025, 1, 1) + timedelta(days=np.random.randint(0, 60))
        avail_end = avail_start + timedelta(days=np.random.randint(180, 365))

        vessels.append({
            "name": name,
            "vessel_class": vc,
            "capacity": round(np.random.uniform(*spec["capacity_range"]), 0),
            "draft": round(np.random.uniform(*spec["draft"]), 1),
            "loa": round(np.random.uniform(*spec["loa"]), 1),
            "beam": round(np.random.uniform(*spec["beam"]), 1),
            "available_from": avail_start,
            "available_until": avail_end,
            "speed_knots": round(np.random.uniform(12.0, 15.5), 1),
            "fuel_consumption_tons_per_day": round(np.random.uniform(25.0, 45.0), 1),
            "daily_hire_rate": round(np.random.uniform(12000, 25000), 0),
        })

    return vessels


def generate_congestion_data(ports_data, start_date=date(2024, 1, 1), end_date=date(2025, 12, 31)):
    np.random.seed(46)
    records = []
    current = start_date

    while current <= end_date:
        for port in ports_data:
            day_of_year = current.timetuple().tm_yday
            seasonal = 15 * np.sin(2 * np.pi * (day_of_year - 30) / 365)
            base = 30
            congestion = base + seasonal + np.random.normal(0, 10)
            congestion = max(0, min(100, congestion))
            delay = congestion * 0.5 + np.random.normal(0, 3)

            records.append({
                "date": current,
                "port_name": port["name"],
                "congestion_index": round(congestion, 1),
                "expected_delay_hours": round(max(0, delay), 1),
                "vessels_waiting": max(0, int(congestion / 15))
            })
        current += timedelta(days=1)

    return pd.DataFrame(records)


def seed_database():
    init_db()
    db = SessionLocal()

    try:
        print("Generating synthetic freight rates...")
        freight_df = generate_synthetic_freight_rates()
        freight_df.to_sql("freight_rates", engine, if_exists="append", index=False, chunksize=5000)
        print(f"  Inserted {len(freight_df)} freight rate records")

        print("Generating synthetic commodity prices...")
        commodity_df = generate_synthetic_commodity_prices()
        commodity_df.to_sql("commodity_prices", engine, if_exists="append", index=False)
        print(f"  Inserted {len(commodity_df)} commodity price records")

        print("Generating synthetic bunker prices...")
        bunker_df = generate_synthetic_bunker_prices()
        bunker_df.to_sql("bunker_prices", engine, if_exists="append", index=False, chunksize=5000)
        print(f"  Inserted {len(bunker_df)} bunker price records")

        print("Inserting ports...")
        ports_data = generate_ports()
        for p in ports_data:
            port = Port(**p)
            db.add(port)
        db.commit()

        print("Inserting vessels...")
        vessels_data = generate_vessels()
        for v in vessels_data:
            vessel = Vessel(**v)
            db.add(vessel)
        db.commit()

        print("Generating congestion data...")
        congestion_df = generate_congestion_data(ports_data)

        port_name_to_id = {p.name: p.port_id for p in db.query(Port).all()}
        congestion_df["port_id"] = congestion_df["port_name"].map(port_name_to_id)
        congestion_df = congestion_df.drop(columns=["port_name"])
        congestion_df = congestion_df.dropna(subset=["port_id"])
        congestion_df["port_id"] = congestion_df["port_id"].astype(int)
        congestion_df.to_sql("port_congestion", engine, if_exists="append", index=False, chunksize=5000)
        print(f"  Inserted {len(congestion_df)} congestion records")

        print("Inserting sample cargo requirement...")
        cargo = CargoRequirement(
            commodity="Thermal Coal",
            quantity=75000,
            origin="Australia",
            destination="Paradip",
            laycan_start=date(2025, 10, 10),
            laycan_end=date(2025, 10, 20),
            required_delivery_date=date(2025, 11, 15),
            required_voyages=6
        )
        db.add(cargo)

        print("Inserting sample contracts...")
        contracts_data = [
            {"contract_type": "spot", "voyages": 1, "freight_rate": 22.5, "vessel_class": "panamax",
             "route": "Australia-Paradip", "start_date": date(2025, 10, 1), "end_date": date(2025, 10, 31)},
            {"contract_type": "short_term", "duration_months": 3, "voyages": 3, "freight_rate": 21.0,
             "vessel_class": "panamax", "route": "Australia-Paradip", "start_date": date(2025, 10, 1),
             "end_date": date(2026, 1, 31)},
            {"contract_type": "medium_term", "duration_months": 6, "voyages": 6, "freight_rate": 19.5,
             "vessel_class": "panamax", "route": "Australia-Paradip", "start_date": date(2025, 10, 1),
             "end_date": date(2026, 4, 30)},
            {"contract_type": "medium_term", "duration_months": 12, "voyages": 12, "freight_rate": 18.5,
             "vessel_class": "panamax", "route": "Australia-Paradip", "start_date": date(2025, 10, 1),
             "end_date": date(2026, 10, 31)},
        ]
        for c in contracts_data:
            contract = Contract(**c)
            db.add(contract)
        db.commit()

        print("Database seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
