from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    _db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "maritime.db")
    DATABASE_URL = f"sqlite:///{_db_path}"
    print(f"[DB] No DATABASE_URL set — using SQLite at {_db_path}")
else:
    print(f"[DB] Using: {DATABASE_URL}")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    **({"pool_size": 10, "max_overflow": 20} if "sqlite" not in DATABASE_URL else {}),
    connect_args=connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Additive columns introduced by the $0 live-sync reconfigure.
# create_all() never alters existing tables, so backfill them here.
_MIGRATION_COLUMNS = {
    "freight_rates": [("fetched_at", "TIMESTAMP")],
    "commodity_prices": [("source", "VARCHAR(100)"), ("fetched_at", "TIMESTAMP")],
    "bunker_prices": [("source", "VARCHAR(100)"), ("fetched_at", "TIMESTAMP")],
    "port_congestion": [("source", "VARCHAR(100)"), ("fetched_at", "TIMESTAMP")],
    "vessels": [
        ("imo", "VARCHAR(20)"), ("mmsi", "VARCHAR(20)"),
        ("last_lat", "FLOAT"), ("last_lon", "FLOAT"),
        ("last_ais_at", "TIMESTAMP"),
        ("destination_raw", "VARCHAR(100)"), ("eta_raw", "VARCHAR(100)"),
        ("availability_proxy", "VARCHAR(50)"),
    ],
}


def _migrate_additive_columns():
    from sqlalchemy import inspect, text
    try:
        insp = inspect(engine)
        existing_tables = set(insp.get_table_names())
        with engine.begin() as conn:
            dialect = engine.dialect.name
            for table, cols in _MIGRATION_COLUMNS.items():
                if table not in existing_tables:
                    continue
                try:
                    present = {c["name"] for c in insp.get_columns(table)}
                except Exception:
                    continue
                for col, coltype in cols:
                    if col in present:
                        continue
                    try:
                        if dialect == "postgresql":
                            conn.execute(text(
                                f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{col}" {coltype}'
                            ))
                        else:
                            conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {coltype}'))
                        print(f"[DB] migrated: {table}.{col}")
                    except Exception as e:
                        print(f"[DB] migration skipped {table}.{col}: {e}")
    except Exception as e:
        print(f"[DB] migration check skipped: {e}")


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_additive_columns()
