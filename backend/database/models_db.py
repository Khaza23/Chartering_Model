from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, Enum as SAEnum,
    UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .postgres import Base
import enum


class VesselClass(str, enum.Enum):
    PANAMAX = "panamax"
    SUPRAMAX = "supramax"
    HANDYMAX = "handymax"
    CAPESIZE = "capesize"
    VLOC = "vloc"


class ContractType(str, enum.Enum):
    SPOT = "spot"
    SHORT_TERM = "short_term"  # 3-6 voyages
    MEDIUM_TERM = "medium_term"  # 6-12 voyages


class RecommendationAction(str, enum.Enum):
    BOOK_NOW = "book_now"
    WAIT = "wait"
    SHORT_CONTRACT = "short_contract"
    MEDIUM_CONTRACT = "medium_contract"
    SWITCH_ROUTE = "switch_route"


class FreightRate(Base):
    __tablename__ = "freight_rates"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    route = Column(String(100), nullable=False, index=True)
    vessel_class = Column(String(50), nullable=False, index=True)
    rate_usd_per_ton = Column(Float, nullable=False)
    source = Column(String(100), default="synthetic")
    fetched_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_freight_route_date", "route", "date"),
    )


class CommodityPrice(Base):
    __tablename__ = "commodity_prices"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    coal_price = Column(Float)
    steel_price = Column(Float)
    iron_ore_price = Column(Float)
    index_value = Column(Float)
    source = Column(String(100), default="synthetic")
    fetched_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("date", name="uq_commodity_date"),
    )


class BunkerPrice(Base):
    __tablename__ = "bunker_prices"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    port = Column(String(100), nullable=False, index=True)
    vlsfo_price = Column(Float)
    mgo_price = Column(Float)
    source = Column(String(100), default="synthetic")
    fetched_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_bunker_port_date", "port", "date"),
    )


class Port(Base):
    __tablename__ = "ports"

    port_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    country = Column(String(100))
    region = Column(String(100))
    draft_limit = Column(Float, nullable=False)  # meters
    loa_limit = Column(Float, nullable=False)  # meters
    beam_limit = Column(Float, nullable=False)  # meters
    berth_capacity = Column(Integer)  # max vessels at berth
    avg_turnaround_hours = Column(Float)
    cargo_handling_rate = Column(Float)  # tons/hour

    congestion_records = relationship("PortCongestion", back_populates="port")


class Vessel(Base):
    __tablename__ = "vessels"

    vessel_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    vessel_class = Column(String(50), nullable=False, index=True)
    capacity = Column(Float, nullable=False)  # DWT in tons
    draft = Column(Float, nullable=False)  # meters
    loa = Column(Float, nullable=False)  # meters overall
    beam = Column(Float, nullable=False)  # meters
    available_from = Column(Date, nullable=False)
    available_until = Column(Date, nullable=False)
    speed_knots = Column(Float)
    fuel_consumption_tons_per_day = Column(Float)
    daily_hire_rate = Column(Float)
    # Live AIS-derived fields ($0 proxy, not commercial fixture data)
    imo = Column(String(20), nullable=True)
    mmsi = Column(String(20), nullable=True)
    last_lat = Column(Float, nullable=True)
    last_lon = Column(Float, nullable=True)
    last_ais_at = Column(DateTime, nullable=True)
    destination_raw = Column(String(100), nullable=True)
    eta_raw = Column(String(100), nullable=True)
    availability_proxy = Column(String(50), nullable=True)  # open | laden | unknown


class PortCongestion(Base):
    __tablename__ = "port_congestion"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    port_id = Column(Integer, ForeignKey("ports.port_id"), nullable=False)
    congestion_index = Column(Float)  # 0-100
    expected_delay_hours = Column(Float)
    vessels_waiting = Column(Integer)
    source = Column(String(100), default="synthetic")
    fetched_at = Column(DateTime, server_default=func.now())

    port = relationship("Port", back_populates="congestion_records")

    __table_args__ = (
        Index("ix_congestion_port_date", "port_id", "date"),
    )


class CargoRequirement(Base):
    __tablename__ = "cargo_requirements"

    cargo_id = Column(Integer, primary_key=True, index=True)
    commodity = Column(String(100), nullable=False)
    quantity = Column(Float, nullable=False)  # MT
    origin = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False, index=True)
    laycan_start = Column(Date, nullable=False)
    laycan_end = Column(Date, nullable=False)
    required_delivery_date = Column(Date)
    required_voyages = Column(Integer, default=1)


class Contract(Base):
    __tablename__ = "contracts"

    contract_id = Column(Integer, primary_key=True, index=True)
    contract_type = Column(String(50), nullable=False)
    duration_months = Column(Integer)
    voyages = Column(Integer)
    freight_rate = Column(Float)  # USD/MT
    contract_type_detail = Column(String(50))
    vessel_class = Column(String(50))
    route = Column(String(100))
    start_date = Column(Date)
    end_date = Column(Date)


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, index=True)
    forecast_date = Column(Date, nullable=False, index=True)
    route = Column(String(100), nullable=False)
    vessel_class = Column(String(50), nullable=False)
    forecast_value = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=False)
    upper_bound = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)  # 0-1
    model_version = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_forecast_route_date", "route", "forecast_date"),
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    cargo_id = Column(Integer, ForeignKey("cargo_requirements.cargo_id"))
    action = Column(String(50), nullable=False)
    vessel_id = Column(Integer, ForeignKey("vessels.vessel_id"))
    port_id = Column(Integer, ForeignKey("ports.port_id"))
    contract_type = Column(String(50))
    voyage_count = Column(Integer)
    expected_cost_usd = Column(Float)
    cost_per_mt = Column(Float)
    risk_score = Column(Float)
    confidence = Column(Float)
    expected_savings_usd = Column(Float)
    reasoning = Column(Text)
    model_version = Column(String(50))
    user_action = Column(String(50))  # approve/modify/reject
    user_notes = Column(Text)


class SyncRun(Base):
    """Audit log for $0 live-sync jobs. Powers GET /api/data-status."""

    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    dataset = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="success")  # success | failed | skipped
    rows_upserted = Column(Integer, default=0)
    error = Column(Text, nullable=True)
