from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import pandas as pd
import json
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.postgres import get_db, init_db, engine
from database.models_db import (
    FreightRate, Port, Vessel, PortCongestion, CargoRequirement,
    Contract, Forecast, Recommendation
)
from data.preprocessing import (
    load_freight_rates, load_commodity_prices, load_bunker_prices,
    load_congestion, load_vessels, load_ports, load_contracts,
    load_cargo_requirements, create_features
)
from data.realtime_fetcher import (
    fetch_freight_realtime, fetch_commodity_realtime, fetch_bunker_realtime,
    fetch_congestion_realtime, fetch_vessels_realtime, fetch_all_realtime
)
from models.forecast_model import FreightForecaster
from optimization.feasibility import FeasibilityEngine
from optimization.cost_engine import CostEngine
from risk.risk_engine import RiskEngine
from optimization.optimizer import CharteringOptimizer
from optimization.timing import TimingAdvisor
import numpy as np

def to_serializable(val):
    if isinstance(val, dict):
        return {str(k): to_serializable(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [to_serializable(v) for v in val]
    elif hasattr(val, '__dict__') and not isinstance(val, type):
        return to_serializable(vars(val))
    elif isinstance(val, (np.floating, float)):
        return float(val)
    elif isinstance(val, (np.integer, int)):
        return int(val)
    elif isinstance(val, (np.bool_, bool)):
        return bool(val)
    elif isinstance(val, np.ndarray):
        return [to_serializable(v) for v in val.tolist()]
    return val

app = FastAPI(
    title="Maritime Chartering Decision Engine",
    description="AI-powered vessel chartering optimization for dry bulk procurement",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ForecastRequest(BaseModel):
    route: str = "Australia-Paradip"
    vessel_class: str = "panamax"
    forecast_days: int = Field(default=30, ge=1, le=365)


class FeasibilityRequest(BaseModel):
    cargo_quantity: float = 75000
    origin: str = "Australia"
    destination: str = "Paradip"
    laycan_start: date = date(2025, 10, 10)
    laycan_end: date = date(2025, 10, 20)
    num_ships: int = Field(default=1, ge=1, le=20)


class CostRequest(BaseModel):
    cargo_quantity: float = 75000
    vessel_id: int = 1
    port_name: str = "Paradip"
    origin: str = "Australia"
    num_ships: int = Field(default=1, ge=1, le=20)


class OptimizationRequest(BaseModel):
    cargo_quantity: float = 75000
    origin: str = "Australia"
    destination: str = "Paradip"
    laycan_start: date = date(2025, 10, 10)
    laycan_end: date = date(2025, 10, 20)
    required_voyages: int = 6
    num_ships: int = Field(default=1, ge=1, le=20)


def resolve_current_rate(db: Session, origin: str, destination: str,
                         vessel_class: str = "panamax"):
    """Return (rate, source). Always live market last close — no user override."""
    route = f"{origin}-{destination}"
    try:
        live_df = fetch_freight_realtime(db, route=route, vessel_class=vessel_class)
        if live_df is not None and not live_df.empty and "rate_usd_per_ton" in live_df.columns:
            return float(live_df["rate_usd_per_ton"].iloc[-1]), "live"
    except Exception:
        pass
    try:
        any_df = fetch_freight_realtime(db)
        if any_df is not None and not any_df.empty:
            return float(any_df["rate_usd_per_ton"].iloc[-1]), "live_fallback"
    except Exception:
        pass
    return 22.0, "fallback"


# ── Fleet helpers: cargo_quantity is the TOTAL program quantity per lifting
# cycle; num_ships splits it into per-ship parcels the optimizer can price
# with its existing single-vessel math (num_ships=1 == legacy behaviour). ──
REF_PARCEL_MT = 75000.0  # typical Panamax parcel used for suggestions


def split_cargo(total_quantity: float, num_ships: int):
    """Return (per_ship_qty, fleet_size). Guards against bad input."""
    try:
        n = int(num_ships or 1)
    except Exception:
        n = 1
    n = max(1, min(20, n))
    try:
        total = float(total_quantity or 0)
    except Exception:
        total = 0.0
    total = max(0.0, total)
    return (round(total / n, 2) if n and total > 0 else 0.0), n


def suggest_fleet(total_quantity: float, ref_capacity: float = REF_PARCEL_MT):
    """Suggest ship count so each parcel fits a typical vessel.

    Returns {suggested_ships, per_ship_quantity, ...}. Pure math helper —
    the /optimize response refines it with the winning vessel's capacity.
    """
    try:
        total = float(total_quantity or 0)
    except Exception:
        total = 0.0
    try:
        ref = float(ref_capacity or REF_PARCEL_MT)
    except Exception:
        ref = REF_PARCEL_MT
    if ref <= 0:
        ref = REF_PARCEL_MT
    if total <= 0:
        return {"suggested_ships": 1, "per_ship_quantity": 0.0,
                "reference_capacity": round(ref, 0), "total_quantity": 0.0}
    import math
    n = max(1, min(20, int(math.ceil(total / ref))))
    return {"suggested_ships": n,
            "per_ship_quantity": round(total / n, 0),
            "reference_capacity": round(ref, 0),
            "total_quantity": round(total, 0)}


class ScenarioRequest(BaseModel):
    base_params: OptimizationRequest
    freight_change_pct: float = 0
    bunker_change_pct: float = 0
    congestion_change: float = 0
    delay_change_hours: float = 0


class TimingRequest(BaseModel):
    base_params: OptimizationRequest
    wait_days: List[int] = [0, 7, 14, 30, 45, 60]


class RecommendationAction(BaseModel):
    recommendation_id: int
    action: str = Field(..., pattern="^(approve|modify|reject)$")
    notes: Optional[str] = None


_scheduler = None


def _start_background_sync():
    """APScheduler (in-process, $0): daily freight/bunker, weekly commodities,
    hourly AIS-derived congestion snapshot. All jobs fail soft."""
    global _scheduler
    if os.getenv("SYNC_DAILY", "true").lower() not in ("1", "true", "yes"):
        print("[SYNC] SYNC_DAILY disabled — scheduler skipped.")
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as e:
        print(f"[SYNC] apscheduler not installed ({e}) — scheduler skipped.")
        return
    if _scheduler is not None:
        return
    try:
        from data import sync_service

        def _job_all():
            try:
                print("[SYNC] scheduled sync_all starting...")
                print(sync_service.sync_all())
            except Exception as e:
                print(f"[SYNC] scheduled sync failed: {e}")

        def _job_congestion():
            try:
                from data.connectors.ais_worker import (
                    get_live_port_metrics, get_live_vessel_updates,
                )
                n = sync_service.sync_congestion_from_live_metrics(get_live_port_metrics())
                sync_service.sync_vessel_positions(get_live_vessel_updates())
                if n:
                    print(f"[SYNC] congestion snapshot upserted: {n} rows")
            except Exception as e:
                print(f"[SYNC] congestion job skipped: {e}")

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(_job_all, "interval", hours=24, id="daily_all", replace_existing=True)
        _scheduler.add_job(_job_congestion, "interval", hours=1, id="hourly_congestion", replace_existing=True)
        _scheduler.start()
        print("[SYNC] scheduler started (daily all, hourly congestion).")
    except Exception as e:
        print(f"[SYNC] scheduler start failed: {e}")


def _maybe_start_ais():
    try:
        from data.connectors.ais_worker import start_ais_worker
        from database.postgres import SessionLocal as _SL
        from database.models_db import Vessel as _V
        db = _SL()
        try:
            mmsis = [r[0] for r in db.query(_V.mmsi).filter(_V.mmsi.isnot(None)).limit(100).all()]
        finally:
            db.close()
        start_ais_worker([m for m in mmsis if m])
    except Exception as e:
        print(f"[AIS] worker start skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        from database.postgres import SessionLocal
        db = SessionLocal()
        count = db.query(FreightRate).count()
        db.close()
        if count == 0:
            print("[STARTUP] Empty database — seeding synthetic baseline...")
            from data.ingestion import seed_database
            seed_database()
            print("[STARTUP] Seeding complete.")
        else:
            print(f"[STARTUP] Database has {count} freight rate records — skipping seed.")
        # Backfill demo IMO/MMSI for vessels seeded before the AIS reconfigure.
        try:
            from database.models_db import Vessel
            db2 = SessionLocal()
            try:
                updated = 0
                for i, v in enumerate(db2.query(Vessel).filter(Vessel.mmsi.is_(None)).order_by(Vessel.vessel_id).all()):
                    v.imo = v.imo or str(9000000 + (v.vessel_id or i))
                    v.mmsi = str(400000000 + (v.vessel_id or i))
                    v.availability_proxy = v.availability_proxy or "unknown"
                    updated += 1
                if updated:
                    db2.commit()
                    print(f"[STARTUP] Backfilled IMO/MMSI for {updated} vessels.")
            finally:
                db2.close()
        except Exception as e:
            print(f"[STARTUP] IMO/MMSI backfill skipped: {e}")
    except Exception as e:
        print(f"[STARTUP] Error: {e}")
    # Reconfigure-only addition: opportunistic $0 live sync + background jobs.
    try:
        if os.getenv("SYNC_ON_BOOT", "true").lower() in ("1", "true", "yes"):
            from data import sync_service
            print(f"[STARTUP] SYNC_ON_BOOT sync: {sync_service.sync_all()}")
        _maybe_start_ais()
        _start_background_sync()
    except Exception as e:
        print(f"[STARTUP] live-sync skipped: {e}")
    yield
    try:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
    except Exception:
        pass
    try:
        from data.connectors.ais_worker import stop_ais_worker
        stop_ais_worker()
    except Exception:
        pass


app.router.lifespan_context = lifespan


@app.get("/")
async def root():
    return {
        "name": "Maritime Chartering Decision Engine",
        "version": "1.0.0",
        "endpoints": {
            "forecast": "/api/forecast",
            "feasibility": "/api/feasibility",
            "cost": "/api/cost",
            "optimize": "/api/optimize",
            "scenario": "/api/scenario",
            "recommendation": "/api/recommendation",
            "vessels": "/api/vessels",
            "ports": "/api/ports",
            "health": "/api/health",
            "sync": "/api/sync",
            "data_status": "/api/data-status"
        }
    }


@app.get("/api/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": str(e)}


@app.post("/api/forecast")
async def get_forecast(request: ForecastRequest, db: Session = Depends(get_db)):
    try:
        freight_df = fetch_freight_realtime(db, route=request.route, vessel_class=request.vessel_class)
        if freight_df.empty:
            raise HTTPException(status_code=404, detail="No freight data found")

        commodity_df = fetch_commodity_realtime(db)
        bunker_df = fetch_bunker_realtime(db)

        featured_df = create_features(freight_df, commodity_df, bunker_df)

        forecaster = FreightForecaster()
        forecaster.train(featured_df, request.route, request.vessel_class)

        forecasts = forecaster.predict(
            featured_df, forecast_days=request.forecast_days,
            route=request.route, vessel_class=request.vessel_class
        )

        current_rate = float(freight_df["rate_usd_per_ton"].iloc[-1])
        forecast_values = [f.forecast_value for f in forecasts]
        trend = "rising" if forecast_values[-1] > current_rate * 1.02 else (
            "falling" if forecast_values[-1] < current_rate * 0.98 else "stable"
        )

        volatility = float(freight_df["rate_usd_per_ton"].tail(30).std() /
                          freight_df["rate_usd_per_ton"].tail(30).mean())

        result = {
            "route": request.route,
            "vessel_class": request.vessel_class,
            "current_rate": current_rate,
            "forecast": {
                "value": forecasts[0].forecast_value if forecasts else current_rate,
                "lower_bound": forecasts[0].lower_bound if forecasts else current_rate * 0.85,
                "upper_bound": forecasts[0].upper_bound if forecasts else current_rate * 1.15,
                "confidence": forecasts[0].confidence if forecasts else 0.7,
                "trend": trend
            },
            "volatility": round(volatility, 4),
            "forecast_range": [
                {
                    "date": f.forecast_date.isoformat() if isinstance(f.forecast_date, date) else str(f.forecast_date),
                    "value": f.forecast_value,
                    "lower": f.lower_bound,
                    "upper": f.upper_bound,
                    "confidence": f.confidence
                } for f in forecasts
            ],
            "model_info": {
                "prophet_weight": forecaster.prophet_weight,
                "xgboost_weight": forecaster.xgboost_weight,
                "training_points": len(featured_df)
            }
        }

        return to_serializable(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feasibility")
async def get_feasibility(request: FeasibilityRequest, db: Session = Depends(get_db)):
    try:
        vessels_df = fetch_vessels_realtime(db)
        ports_df = load_ports(db)
        congestion_df = fetch_congestion_realtime(db)

        per_ship_qty, fleet_n = split_cargo(request.cargo_quantity, request.num_ships)
        engine = FeasibilityEngine()
        feasible_vessels = engine.filter_vessels(
            vessels_df, ports_df, per_ship_qty,
            request.laycan_start, request.laycan_end,
            request.origin, request.destination
        )

        port_scores = []
        if feasible_vessels:
            port_scores = engine.score_port_feasibility(
                ports_df, congestion_df, feasible_vessels[0]
            )

        total_vessels = len(vessels_df)
        feasible_count = len(feasible_vessels)
        rejected_count = total_vessels * len(ports_df) - feasible_count
        unique_feasible_vessels = len({v.vessel_id for v in feasible_vessels})

        _ref_cap = REF_PARCEL_MT
        try:
            if not vessels_df.empty and "capacity" in vessels_df.columns:
                _caps = vessels_df["capacity"].dropna()
                _caps = _caps[_caps > 0]
                if "vessel_class" in vessels_df.columns:
                    _pana = vessels_df[vessels_df["vessel_class"] == "panamax"]["capacity"].dropna()
                    _pana = _pana[_pana > 0]
                    if not _pana.empty:
                        _caps = _pana
                if not _caps.empty:
                    _ref_cap = float(_caps.median())
        except Exception:
            pass
        return {
            "input": {
                "cargo_quantity": request.cargo_quantity,
                "origin": request.origin,
                "destination": request.destination,
                "laycan": f"{request.laycan_start} to {request.laycan_end}"
            },
            "fleet": {
                "num_ships": fleet_n,
                "total_quantity": round(float(request.cargo_quantity or 0), 0),
                "per_ship_quantity": per_ship_qty,
                "suggestion": suggest_fleet(request.cargo_quantity, _ref_cap),
            },
            "summary": {
                "total_candidates": total_vessels * len(ports_df),
                "feasible_count": feasible_count,
                "rejected_count": rejected_count,
                "filter_pass_rate": round(feasible_count / max(total_vessels * len(ports_df), 1) * 100, 1),
                "unique_feasible_vessels": unique_feasible_vessels,
                "total_vessels": total_vessels
            },
            "feasible_vessels": [
                {
                    "vessel_id": v.vessel_id,
                    "name": v.name,
                    "vessel_class": v.vessel_class,
                    "capacity": v.capacity,
                    "draft": v.draft,
                    "loa": v.loa,
                    "beam": v.beam,
                    "port_id": v.port_id,
                    "port_name": v.port_name,
                    "feasibility_score": v.feasibility_score,
                    "daily_hire_rate": v.daily_hire_rate,
                    "fuel_consumption": v.fuel_consumption,
                    "speed_knots": v.speed_knots
                } for v in feasible_vessels
            ],
            "port_scores": port_scores
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/cost")
async def get_cost(request: CostRequest, db: Session = Depends(get_db)):
    try:
        resolved_rate, rate_source = resolve_current_rate(
            db, request.origin, request.port_name
        )
        vessels_df = fetch_vessels_realtime(db)
        vessel_row = vessels_df[vessels_df["vessel_id"] == request.vessel_id]

        if vessel_row.empty:
            vessel = type('Vessel', (), {
                'vessel_id': request.vessel_id,
                'name': 'Unknown',
                'vessel_class': 'panamax',
                'capacity': 75000,
                'draft': 14.0,
                'loa': 230,
                'beam': 32,
                'daily_hire_rate': 18000,
                'fuel_consumption': 35,
                'speed_knots': 14.0
            })()
        else:
            vessel = vessel_row.iloc[0]

        bunker_df = fetch_bunker_realtime(db)
        avg_bunker = float(bunker_df["vlsfo_price"].mean()) if not bunker_df.empty else 400.0

        congestion_df = fetch_congestion_realtime(db)
        avg_congestion = float(congestion_df["congestion_index"].mean()) if not congestion_df.empty else 30.0
        avg_delay = float(congestion_df["expected_delay_hours"].mean()) if not congestion_df.empty else 12.0

        per_ship_qty, fleet_n = split_cargo(request.cargo_quantity, request.num_ships)
        cost_engine = CostEngine()
        cost = cost_engine.calculate_total_cost(
            freight_rate_per_ton=resolved_rate,
            cargo_quantity=per_ship_qty,
            vessel=vessel,
            port_name=request.port_name,
            origin=request.origin,
            avg_bunker_price=avg_bunker,
            avg_congestion_index=avg_congestion,
            avg_delay_hours=avg_delay
        )

        contract_options = [
            {"contract_type": "short_term", "freight_rate": resolved_rate * 0.97, "voyages": 3, "duration_months": 2},
            {"contract_type": "medium_term", "freight_rate": resolved_rate * 0.94, "voyages": 6, "duration_months": 4},
            {"contract_type": "medium_term", "freight_rate": resolved_rate * 0.91, "voyages": 12, "duration_months": 8},
        ]

        comparison = cost_engine.compare_contract_costs(
            spot_rate=resolved_rate,
            cargo_quantity=per_ship_qty,
            vessel=vessel,
            port_name=request.port_name,
            origin=request.origin,
            contract_options=contract_options,
            avg_bunker_price=avg_bunker,
            avg_congestion_index=avg_congestion
        )
        try:
            for c in comparison:
                c["total_cost"] = round(float(c.get("total_cost", 0)) * fleet_n, 2)
                c["savings_vs_spot"] = round(float(c.get("savings_vs_spot", 0)) * fleet_n, 2)
            # Fleet-scale the spot breakdown too so the tab stays internally
            # consistent (fleet single-lift cost); cost/mt is unchanged.
            cost.freight_cost = round(cost.freight_cost * fleet_n, 2)
            cost.bunker_cost = round(cost.bunker_cost * fleet_n, 2)
            cost.port_charges = round(cost.port_charges * fleet_n, 2)
            cost.loading_cost = round(cost.loading_cost * fleet_n, 2)
            cost.discharge_cost = round(cost.discharge_cost * fleet_n, 2)
            cost.expected_demurrage = round(cost.expected_demurrage * fleet_n, 2)
            cost.expected_delay_cost = round(cost.expected_delay_cost * fleet_n, 2)
            cost.other_costs = round(cost.other_costs * fleet_n, 2)
            cost.total_cost = round(cost.total_cost * fleet_n, 2)
        except Exception:
            pass

        return to_serializable({
            "resolved_freight_rate": resolved_rate,
            "rate_source": rate_source,
            "fleet": {
                "num_ships": fleet_n,
                "total_quantity": round(float(request.cargo_quantity or 0), 0),
                "per_ship_quantity": per_ship_qty,
                "fleet_total_cost": round(cost.total_cost * fleet_n, 2),
                "suggestion": suggest_fleet(request.cargo_quantity, REF_PARCEL_MT),
            },
            "spot_cost": {
                "total_cost": cost.total_cost,
                "cost_per_mt": cost.cost_per_mt,
                "breakdown": {
                    "freight": cost.freight_cost,
                    "bunker": cost.bunker_cost,
                    "port_charges": cost.port_charges,
                    "loading": cost.loading_cost,
                    "discharge": cost.discharge_cost,
                    "demurrage": cost.expected_demurrage,
                    "delay": cost.expected_delay_cost,
                    "other": cost.other_costs
                }
            },
            "comparison": [
                {
                    "type": c["type"],
                    "voyages": c["voyages"],
                    "freight_rate": c["freight_rate"],
                    "total_cost": c["total_cost"],
                    "cost_per_mt": c["cost_per_mt"],
                    "savings_vs_spot": c["savings_vs_spot"],
                    "savings_pct": c.get("savings_pct", 0)
                } for c in comparison
            ]
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/optimize")
async def optimize(request: OptimizationRequest, db: Session = Depends(get_db)):
    try:
        current_rate, rate_source = resolve_current_rate(
            db, request.origin, request.destination
        )
        freight_df = fetch_freight_realtime(db, route=f"{request.origin}-{request.destination}")
        commodity_df = fetch_commodity_realtime(db)
        bunker_df = fetch_bunker_realtime(db)

        featured_df = create_features(freight_df, commodity_df, bunker_df) if not freight_df.empty else pd.DataFrame()

        forecast = None
        if not featured_df.empty:
            forecaster = FreightForecaster()
            try:
                forecaster.train(featured_df, f"{request.origin}-{request.destination}", "panamax")
                forecasts = forecaster.predict(
                    featured_df, forecast_days=1,
                    route=f"{request.origin}-{request.destination}", vessel_class="panamax"
                )
                if forecasts:
                    forecast = {
                        "forecast_value": forecasts[0].forecast_value,
                        "lower_bound": forecasts[0].lower_bound,
                        "upper_bound": forecasts[0].upper_bound,
                        "confidence": forecasts[0].confidence
                    }
            except Exception:
                pass

        vessels_df = fetch_vessels_realtime(db)
        ports_df = load_ports(db)
        contracts_df = load_contracts(db)
        congestion_df = fetch_congestion_realtime(db)

        avg_congestion = float(congestion_df["congestion_index"].mean()) if not congestion_df.empty else 30
        avg_delay = float(congestion_df["expected_delay_hours"].mean()) if not congestion_df.empty else 12

        bunker_avg = float(bunker_df["vlsfo_price"].mean()) if not bunker_df.empty else 400

        per_ship_qty, fleet_n = split_cargo(request.cargo_quantity, request.num_ships)
        optimizer = CharteringOptimizer()
        result = optimizer.optimize(
            cargo_quantity=per_ship_qty,
            origin=request.origin,
            destination=request.destination,
            laycan_start=request.laycan_start,
            laycan_end=request.laycan_end,
            vessels_df=vessels_df,
            ports_df=ports_df,
            freight_forecast=forecast,
            current_freight_rate=current_rate,
            contracts_df=contracts_df,
            port_congestion=avg_congestion,
            port_avg_delay=avg_delay,
            avg_bunker_price=bunker_avg,
            required_voyages=request.required_voyages,
            congestion_df=congestion_df
        )

        # Fleet scaling: optimizer prices ONE ship's parcel (per_ship_qty);
        # the fleet total is that program cost x num_ships. cost/mt is unchanged.
        fleet_total = round(float(result.expected_total_cost or 0) * fleet_n, 2)
        fleet_savings = round(float(result.expected_savings or 0) * fleet_n, 2)
        scaled_options = []
        try:
            for o in (result.all_options or []):
                c = dict(o)
                c["total_cost"] = round(float(o.get("total_cost", 0)) * fleet_n, 2)
                c["savings_vs_spot"] = round(float(o.get("savings_vs_spot", 0)) * fleet_n, 2)
                scaled_options.append(c)
        except Exception:
            scaled_options = result.all_options
        scaled_vessel_options = []
        try:
            for o in (result.vessel_options or []):
                c = dict(o)
                c["total_cost"] = round(float(o.get("total_cost", 0)) * fleet_n, 2)
                scaled_vessel_options.append(c)
        except Exception:
            scaled_vessel_options = result.vessel_options

        # Refine ship suggestion with the winning vessel's capacity when known.
        _win_cap = 0
        try:
            _win_cap = float((result.recommended_vessel or {}).get("capacity", 0) or 0)
        except Exception:
            _win_cap = 0
        _ref = _win_cap if _win_cap > 0 else REF_PARCEL_MT
        fleet_suggestion = suggest_fleet(request.cargo_quantity, _ref)
        fleet_reasoning = list(result.reasoning or [])
        if fleet_n > 1:
            fleet_reasoning.append(
                f"Fleet plan: {fleet_n} ships x {per_ship_qty:,.0f} MT = "
                f"{float(request.cargo_quantity or 0):,.0f} MT total; "
                f"costs shown are fleet totals ({result.voyage_count} voyages each)."
            )
        elif fleet_suggestion.get("suggested_ships", 1) > 1 and result.recommended_action != "NO_FEASIBLE_SOLUTION":
            fleet_reasoning.append(
                f"Suggestion: {float(request.cargo_quantity or 0):,.0f} MT needs ~"
                f"{fleet_suggestion['suggested_ships']} ships "
                f"({fleet_suggestion['per_ship_quantity']:,.0f} MT each at ~"
                f"{fleet_suggestion['reference_capacity']:,.0f} MT/ship) — "
                f"raise 'Ships' to split the parcel."
            )

        rec_id = None
        if result.recommended_vessel.get("id"):
            from database.models_db import Port
            port_row = db.query(Port).filter(Port.name == result.recommended_port).first()
            if port_row is not None:
                rec = Recommendation(
                    cargo_id=1,
                    action=result.recommended_action,
                    vessel_id=result.recommended_vessel.get("id", 0),
                    port_id=port_row.port_id,
                    contract_type=result.recommended_contract,
                    voyage_count=result.voyage_count,
                    expected_cost_usd=fleet_total,
                    cost_per_mt=result.cost_per_mt,
                    risk_score=result.risk_score,
                    confidence=result.confidence,
                    expected_savings_usd=fleet_savings,
                    reasoning=json.dumps(fleet_reasoning),
                    model_version="ensemble_v1"
                )
                db.add(rec)
                db.commit()
                db.refresh(rec)
                rec_id = rec.id

        return to_serializable({
            "recommendation_id": rec_id,
            "resolved_freight_rate": current_rate,
            "rate_source": rate_source,
            "action": result.recommended_action,
            "vessel": result.recommended_vessel,
            "port": result.recommended_port,
            "contract_type": result.recommended_contract,
            "voyage_count": result.voyage_count,
            "expected_total_cost": fleet_total,
            "cost_per_mt": result.cost_per_mt,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "confidence": result.confidence,
            "expected_savings": fleet_savings,
            "savings_pct": result.savings_pct,
            "all_options": scaled_options,
            "vessel_options": scaled_vessel_options,
            "reasoning": fleet_reasoning,
            "feature_importance": result.feature_importance,
            "fleet": {
                "num_ships": fleet_n,
                "total_quantity": round(float(request.cargo_quantity or 0), 0),
                "per_ship_quantity": per_ship_qty,
                "suggestion": fleet_suggestion,
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenario")
async def run_scenario(request: ScenarioRequest, db: Session = Depends(get_db)):
    try:
        bp0 = request.base_params
        base_rate, base_source = resolve_current_rate(
            db, bp0.origin, bp0.destination
        )
        vessels_df = fetch_vessels_realtime(db)
        ports_df = load_ports(db)
        contracts_df = load_contracts(db)
        bunker_df = fetch_bunker_realtime(db)
        congestion_df = fetch_congestion_realtime(db)

        avg_congestion = float(congestion_df["congestion_index"].mean()) if not congestion_df.empty else 30
        avg_delay = float(congestion_df["expected_delay_hours"].mean()) if not congestion_df.empty else 12
        bunker_avg = float(bunker_df["vlsfo_price"].mean()) if not bunker_df.empty else 400

        base_forecast = {
            "forecast_value": base_rate,
            "lower_bound": base_rate * 0.85,
            "upper_bound": base_rate * 1.15,
            "confidence": 0.75
        }

        _per_ship, _fleet_n = split_cargo(
            request.base_params.cargo_quantity,
            getattr(request.base_params, "num_ships", 1)
        )
        base_params = {
            "cargo_quantity": _per_ship,
            "origin": request.base_params.origin,
            "destination": request.base_params.destination,
            "laycan_start": request.base_params.laycan_start,
            "laycan_end": request.base_params.laycan_end,
            "vessels_df": vessels_df,
            "ports_df": ports_df,
            "freight_forecast": base_forecast,
            "current_freight_rate": base_rate,
            "contracts_df": contracts_df,
            "port_congestion": avg_congestion,
            "port_avg_delay": avg_delay,
            "avg_bunker_price": bunker_avg,
            "required_voyages": request.base_params.required_voyages,
            "congestion_df": congestion_df
        }

        scenario_mods = {}
        if request.freight_change_pct != 0:
            scenario_mods["freight_change_pct"] = request.freight_change_pct
        if request.bunker_change_pct != 0:
            scenario_mods["bunker_change_pct"] = request.bunker_change_pct
        if request.congestion_change != 0:
            scenario_mods["congestion_change"] = request.congestion_change
        if request.delay_change_hours != 0:
            scenario_mods["delay_change_hours"] = request.delay_change_hours

        optimizer = CharteringOptimizer()

        base_result = optimizer.optimize(**base_params)
        scenario_result = optimizer.run_scenario(base_params, scenario_mods)

        return to_serializable({
            "resolved_freight_rate": base_rate,
            "rate_source": base_source,
            "fleet": {
                "num_ships": _fleet_n,
                "total_quantity": round(float(request.base_params.cargo_quantity or 0), 0),
                "per_ship_quantity": _per_ship,
            },
            "base_case": {
                "action": base_result.recommended_action,
                "total_cost": round(float(base_result.expected_total_cost or 0) * _fleet_n, 2),
                "risk_score": base_result.risk_score,
                "risk_level": base_result.risk_level,
                "contract_type": base_result.recommended_contract,
                "savings": round(float(base_result.expected_savings or 0) * _fleet_n, 2)
            },
            "scenario": {
                "modifications": scenario_mods,
                "action": scenario_result["result"].recommended_action,
                "total_cost": round(float(scenario_result["result"].expected_total_cost or 0) * _fleet_n, 2),
                "risk_score": scenario_result["result"].risk_score,
                "risk_level": scenario_result["result"].risk_level,
                "contract_type": scenario_result["result"].recommended_contract,
                "savings": round(float(scenario_result["result"].expected_savings or 0) * _fleet_n, 2)
            },
            "impact": {
                "cost_change": round((float(scenario_result["result"].expected_total_cost or 0) - float(base_result.expected_total_cost or 0)) * _fleet_n, 2),
                "cost_change_pct": round(
                    (scenario_result["result"].expected_total_cost - base_result.expected_total_cost) /
                    base_result.expected_total_cost * 100, 1
                ) if base_result.expected_total_cost > 0 else 0,
                "recommendation_changed": base_result.recommended_action != scenario_result["result"].recommended_action
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/timing")
async def assess_timing(request: TimingRequest, db: Session = Depends(get_db)):
    """Book-now vs wait advisor. Additive: reuses the optimizer per wait date,
    changes no existing endpoint."""
    try:
        bp = request.base_params
        base_rate_t, _ = resolve_current_rate(
            db, bp.origin, bp.destination
        )
        waits = sorted({max(0, int(w)) for w in (request.wait_days or [0])})[:8]
        horizon = min(max(waits) + 1 if waits else 1, 92)

        freight_df = fetch_freight_realtime(db, route=f"{bp.origin}-{bp.destination}")
        commodity_df = fetch_commodity_realtime(db)
        bunker_df = fetch_bunker_realtime(db)
        featured_df = create_features(freight_df, commodity_df, bunker_df) if not freight_df.empty else pd.DataFrame()

        curve: List[Dict] = []
        if not featured_df.empty:
            try:
                forecaster = FreightForecaster()
                forecaster.train(featured_df, f"{bp.origin}-{bp.destination}", "panamax")
                preds = forecaster.predict(
                    featured_df, forecast_days=horizon,
                    route=f"{bp.origin}-{bp.destination}", vessel_class="panamax"
                )
                for f in preds:
                    curve.append({
                        "date": f.forecast_date.isoformat() if hasattr(f.forecast_date, "isoformat") else str(f.forecast_date),
                        "forecast_value": f.forecast_value,
                        "lower_bound": f.lower_bound,
                        "upper_bound": f.upper_bound,
                        "confidence": f.confidence,
                    })
            except Exception:
                curve = []

        vessels_df = fetch_vessels_realtime(db)
        ports_df = load_ports(db)
        contracts_df = load_contracts(db)
        congestion_df = fetch_congestion_realtime(db)
        avg_congestion = float(congestion_df["congestion_index"].mean()) if not congestion_df.empty else 30
        avg_delay = float(congestion_df["expected_delay_hours"].mean()) if not congestion_df.empty else 12
        bunker_avg = float(bunker_df["vlsfo_price"].mean()) if not bunker_df.empty else 400

        base_ff = dict(curve[0]) if curve else None
        _t_per_ship, _t_fleet_n = split_cargo(bp.cargo_quantity, getattr(bp, "num_ships", 1))
        advisor = TimingAdvisor()
        result = advisor.advise(
            cargo_quantity=_t_per_ship,
            origin=bp.origin,
            destination=bp.destination,
            laycan_start=bp.laycan_start,
            laycan_end=bp.laycan_end,
            vessels_df=vessels_df,
            ports_df=ports_df,
            contracts_df=contracts_df,
            forecast_curve=curve,
            base_current_rate=base_rate_t,
            base_freight_forecast=base_ff,
            port_congestion=avg_congestion,
            port_avg_delay=avg_delay,
            avg_bunker_price=bunker_avg,
            required_voyages=bp.required_voyages,
            congestion_df=congestion_df,
            wait_days=waits,
        )
        try:
            for o in result.get("options", []):
                if o.get("feasible") and o.get("total_cost") is not None:
                    o["total_cost"] = round(float(o["total_cost"]) * _t_fleet_n, 2)
                if "savings_vs_now" in o:
                    o["savings_vs_now"] = round(float(o.get("savings_vs_now") or 0) * _t_fleet_n, 2)
            v = result.get("verdict")
            if v and "expected_savings_vs_now" in v:
                v["expected_savings_vs_now"] = round(float(v.get("expected_savings_vs_now") or 0) * _t_fleet_n, 2)
            result["fleet"] = {
                "num_ships": _t_fleet_n,
                "total_quantity": round(float(bp.cargo_quantity or 0), 0),
                "per_ship_quantity": _t_per_ship,
            }
        except Exception:
            pass
        return to_serializable(result)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendation/{recommendation_id}")
async def get_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    freight_df = fetch_freight_realtime(db)
    commodity_df = fetch_commodity_realtime(db)
    bunker_df = fetch_bunker_realtime(db)
    congestion_df = fetch_congestion_realtime(db)
    vessels_df = fetch_vessels_realtime(db)

    current_freight = float(freight_df["rate_usd_per_ton"].iloc[-1]) if not freight_df.empty else 0
    avg_bunker = float(bunker_df["vlsfo_price"].mean()) if not bunker_df.empty else 400
    avg_congestion = float(congestion_df["congestion_index"].mean()) if not congestion_df.empty else 30

    vessel_row = vessels_df[vessels_df["vessel_id"] == rec.vessel_id]
    vessel_info = vessel_row.iloc[0].to_dict() if not vessel_row.empty else {}

    return {
        "id": rec.id,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "action": rec.action,
        "vessel_id": rec.vessel_id,
        "vessel_info": vessel_info,
        "contract_type": rec.contract_type,
        "voyage_count": rec.voyage_count,
        "expected_cost_usd": rec.expected_cost_usd,
        "cost_per_mt": rec.cost_per_mt,
        "risk_score": rec.risk_score,
        "confidence": rec.confidence,
        "expected_savings_usd": rec.expected_savings_usd,
        "reasoning": json.loads(rec.reasoning) if rec.reasoning else [],
        "user_action": rec.user_action,
        "user_notes": rec.user_notes,
        "live_market": {
            "current_freight_rate": round(current_freight, 2),
            "avg_bunker_price": round(avg_bunker, 2),
            "avg_congestion_index": round(avg_congestion, 1),
        }
    }


@app.post("/api/recommendation/{recommendation_id}/action")
async def take_action(recommendation_id: int, action: RecommendationAction,
                      db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.user_action = action.action
    rec.user_notes = action.notes
    db.commit()

    return {
        "id": rec.id,
        "user_action": rec.user_action,
        "user_notes": rec.user_notes,
        "message": f"Recommendation {action.action}d successfully"
    }


@app.get("/api/fleet-suggestion")
async def fleet_suggestion(
    total_quantity: float = Query(..., gt=0),
    destination: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Suggest ship count for a total cargo quantity.

    Uses live vessel capacities (median, filtered to destination-feasible
    sizes when possible) so the hint tracks the real fleet, not a constant.
    """
    try:
        vessels_df = fetch_vessels_realtime(db)
        # Anchor on the Panamax median (the app's default class) so a mixed
        # fleet of small coasters can't drag the headline suggestion up to
        # absurd ship counts; fall back to overall median, then the constant.
        ref = REF_PARCEL_MT
        if not vessels_df.empty and "capacity" in vessels_df.columns:
            caps = vessels_df["capacity"].dropna()
            caps = caps[caps > 0]
            try:
                if "vessel_class" in vessels_df.columns:
                    pana = vessels_df[vessels_df["vessel_class"] == "panamax"]["capacity"].dropna()
                    pana = pana[pana > 0]
                    if not pana.empty:
                        caps = pana
            except Exception:
                pass
            if not caps.empty:
                ref = float(caps.median())
        detail = []
        if not vessels_df.empty and "capacity" in vessels_df.columns:
            for vc in ("panamax", "supramax", "handymax", "capesize"):
                grp = vessels_df[vessels_df.get("vessel_class") == vc]["capacity"].dropna() if "vessel_class" in vessels_df.columns else []
                try:
                    if len(grp):
                        import math as _m
                        cap = float(grp.median())
                        n = max(1, min(20, int(_m.ceil(float(total_quantity) / cap))))
                        detail.append({"vessel_class": vc,
                                       "reference_capacity": round(cap, 0),
                                       "ships": n,
                                       "per_ship": round(float(total_quantity) / n, 0)})
                except Exception:
                    continue
        s = suggest_fleet(total_quantity, ref)
        s["by_class"] = detail
        if destination:
            s["destination"] = destination
        return to_serializable(s)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/vessels")
async def list_vessels(
    vessel_class: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    vessels_df = fetch_vessels_realtime(db, vessel_class=vessel_class)
    return {"vessels": vessels_df.to_dict(orient="records"), "count": len(vessels_df)}


@app.get("/api/ports")
async def list_ports(db: Session = Depends(get_db)):
    ports_df = load_ports(db)
    congestion_df = fetch_congestion_realtime(db)

    ports_with_congestion = []
    for _, port in ports_df.iterrows():
        port_data = port.to_dict()
        port_congestion = congestion_df[congestion_df["port_name"] == port["name"]]
        if not port_congestion.empty:
            recent = port_congestion.tail(7)
            port_data["live_congestion"] = {
                "congestion_index": round(float(recent["congestion_index"].mean()), 1),
                "expected_delay_hours": round(float(recent["expected_delay_hours"].mean()), 1),
                "vessels_waiting": int(recent["vessels_waiting"].mean()),
                "source": recent["source"].iloc[-1] if "source" in recent.columns else "unknown"
            }
        else:
            port_data["live_congestion"] = None
        ports_with_congestion.append(port_data)

    return {"ports": ports_with_congestion, "count": len(ports_with_congestion)}


@app.get("/api/contracts")
async def list_contracts(db: Session = Depends(get_db)):
    contracts_df = load_contracts(db)
    # NULLs (e.g. spot duration_months) become NaN, which is not JSON
    # compliant — normalize to None before serializing.
    contracts_df = contracts_df.astype(object).where(contracts_df.notnull(), None)
    return {"contracts": contracts_df.to_dict(orient="records"), "count": len(contracts_df)}


@app.get("/api/congestion")
async def get_congestion(
    port_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    congestion_df = fetch_congestion_realtime(db, port_name=port_name)
    if congestion_df.empty:
        return {"congestion": [], "count": 0}

    recent = congestion_df.tail(30)
    summary = {
        "port": port_name or "all",
        "avg_congestion_index": round(float(recent["congestion_index"].mean()), 1),
        "avg_delay_hours": round(float(recent["expected_delay_hours"].mean()), 1),
        "avg_vessels_waiting": round(float(recent["vessels_waiting"].mean()), 1),
        "data_points": len(recent)
    }

    return {
        "summary": summary,
        "recent_data": recent[["date", "congestion_index", "expected_delay_hours", "vessels_waiting"]].to_dict(orient="records")
    }


@app.post("/api/sync")
async def trigger_sync(dataset: Optional[str] = Query(default=None)):
    """Manual $0 live-sync trigger. ?dataset=freight|bunker|commodities|congestion (omit = all)."""
    try:
        from data import sync_service
        if dataset:
            return to_serializable(sync_service.sync_dataset(dataset))
        return to_serializable(sync_service.sync_all())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data-status")
async def data_status(db: Session = Depends(get_db)):
    """Freshness per dataset for Linear-style Live/Stale badges. Never fails hard."""
    from database.models_db import SyncRun
    from sqlalchemy import func as _func
    out: Dict = {"datasets": {}, "ais": {}}
    try:
        specs = {
            "freight": (FreightRate, "freight_rates"),
            "bunker": (None, "bunker_prices"),
            "commodities": (None, "commodity_prices"),
            "congestion": (PortCongestion, "port_congestion"),
        }
        for name, (model, table) in specs.items():
            try:
                from sqlalchemy import text as _text
                total = int(db.execute(_text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
                try:
                    live = int(db.execute(
                        _text(f"SELECT COUNT(*) FROM {table} WHERE source LIKE 'live/%'")
                    ).scalar() or 0)
                except Exception:
                    live = 0
                try:
                    last = db.execute(
                        _text(f"SELECT MAX(fetched_at) FROM {table}")
                    ).scalar()
                    last_iso = last.isoformat() if hasattr(last, "isoformat") else (str(last) if last else None)
                except Exception:
                    last_iso = None
                last_run = db.query(SyncRun).filter(SyncRun.dataset == name)\
                    .order_by(SyncRun.id.desc()).first()
                out["datasets"][name] = {
                    "total_rows": total,
                    "live_rows": live,
                    "last_fetched_at": last_iso,
                    "last_status": last_run.status if last_run else None,
                    "last_error": (last_run.error[:300] if last_run and last_run.error else None),
                    "stale": (live == 0),
                    "source": "live" if live > 0 else "synthetic",
                }
            except Exception as e:
                out["datasets"][name] = {"error": str(e), "stale": True, "source": "synthetic"}
        try:
            from data.connectors.ais_worker import _last_msg_time
            out["ais"] = {
                "worker_running": bool(_last_msg_time),
                "last_message_ago_s": round(__import__("time").time() - _last_msg_time, 1) if _last_msg_time else None,
            }
        except Exception:
            out["ais"] = {"worker_running": False}
    except Exception as e:
        out["error"] = str(e)
    return to_serializable(out)


@app.post("/api/backtest")
async def run_backtest(
    route: str = Query(default="Australia-Paradip"),
    vessel_class: str = Query(default="panamax"),
    test_months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db)
):
    try:
        freight_df = fetch_freight_realtime(db, route=route, vessel_class=vessel_class)
        commodity_df = fetch_commodity_realtime(db)
        bunker_df = fetch_bunker_realtime(db)

        featured_df = create_features(freight_df, commodity_df, bunker_df)

        forecaster = FreightForecaster()
        metrics = forecaster.backtest(featured_df, route, vessel_class, test_months)

        return {
            "route": route,
            "vessel_class": vessel_class,
            "test_months": test_months,
            "metrics": metrics,
            "data_points": len(freight_df),
            "latest_rate": float(freight_df["rate_usd_per_ton"].iloc[-1]) if not freight_df.empty else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
