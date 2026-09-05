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


def init_db():
    Base.metadata.create_all(bind=engine)
