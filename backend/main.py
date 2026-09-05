from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
import pandas as pd
import json
import sys
import os

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
from models.forecast_model import FreightForecaster
from optimization.feasibility import FeasibilityEngine
from optimization.cost_engine import CostEngine
from risk.risk_engine import RiskEngine
from optimization.optimizer import CharteringOptimizer
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


class CostRequest(BaseModel):
    freight_rate: float = 22.0
    cargo_quantity: float = 75000
    vessel_id: int = 1
    port_name: str = "Paradip"
    origin: str = "Australia"


class OptimizationRequest(BaseModel):
    cargo_quantity: float = 75000
    origin: str = "Australia"
    destination: str = "Paradip"
    laycan_start: date = date(2025, 10, 10)
    laycan_end: date = date(2025, 10, 20)
    required_voyages: int = 6
    current_freight_rate: float = 22.0


class ScenarioRequest(BaseModel):
    base_params: OptimizationRequest
    freight_change_pct: float = 0
    bunker_change_pct: float = 0
    congestion_change: float = 0
    delay_change_hours: float = 0


class RecommendationAction(BaseModel):
    recommendation_id: int
    action: str = Field(..., pattern="^(approve|modify|reject)$")
    notes: Optional[str] = None


@app.on_event("startup")
async def startup():
    try:
        init_db()
        from database.postgres import SessionLocal
        db = SessionLocal()
        count = db.query(FreightRate).count()
        db.close()
        if count == 0:
            print("[STARTUP] Empty database — seeding synthetic data...")
            from data.ingestion import seed_database
            seed_database()
            print("[STARTUP] Seeding complete.")
        else:
            print(f"[STARTUP] Database has {count} freight rate records — skipping seed.")
    except Exception as e:
        print(f"[STARTUP] Error: {e}")


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
            "health": "/api/health"
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
        freight_df = load_freight_rates(db, route=request.route, vessel_class=request.vessel_class)
        if freight_df.empty:
            raise HTTPException(status_code=404, detail="No freight data found")

        commodity_df = load_commodity_prices(db)
        bunker_df = load_bunker_prices(db)

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
        vessels_df = load_vessels(db)
        ports_df = load_ports(db)
        congestion_df = load_congestion(db)

        engine = FeasibilityEngine()
        feasible_vessels = engine.filter_vessels(
            vessels_df, ports_df, request.cargo_quantity,
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

        return {
            "input": {
                "cargo_quantity": request.cargo_quantity,
                "origin": request.origin,
                "destination": request.destination,
                "laycan": f"{request.laycan_start} to {request.laycan_end}"
            },
            "summary": {
                "total_candidates": total_vessels * len(ports_df),
                "feasible_count": feasible_count,
                "rejected_count": rejected_count,
                "filter_pass_rate": round(feasible_count / max(total_vessels * len(ports_df), 1) * 100, 1)
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
        vessels_df = load_vessels(db)
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

        cost_engine = CostEngine()
        cost = cost_engine.calculate_total_cost(
            freight_rate_per_ton=request.freight_rate,
            cargo_quantity=request.cargo_quantity,
            vessel=vessel,
            port_name=request.port_name,
            origin=request.origin
        )

        contract_options = [
            {"contract_type": "short_term", "freight_rate": request.freight_rate * 0.97, "voyages": 3, "duration_months": 2},
            {"contract_type": "medium_term", "freight_rate": request.freight_rate * 0.94, "voyages": 6, "duration_months": 4},
            {"contract_type": "medium_term", "freight_rate": request.freight_rate * 0.91, "voyages": 12, "duration_months": 8},
        ]

        comparison = cost_engine.compare_contract_costs(
            spot_rate=request.freight_rate,
            cargo_quantity=request.cargo_quantity,
            vessel=vessel,
            port_name=request.port_name,
            origin=request.origin,
            contract_options=contract_options
        )

        return to_serializable({
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
        freight_df = load_freight_rates(db, route=f"{request.origin}-{request.destination}")
        commodity_df = load_commodity_prices(db)
        bunker_df = load_bunker_prices(db)

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

        vessels_df = load_vessels(db)
        ports_df = load_ports(db)
        contracts_df = load_contracts(db)
        congestion_df = load_congestion(db)

        avg_congestion = float(congestion_df["congestion_index"].mean()) if not congestion_df.empty else 30
        avg_delay = float(congestion_df["expected_delay_hours"].mean()) if not congestion_df.empty else 12

        bunker_avg = float(bunker_df["vlsfo_price"].mean()) if not bunker_df.empty else 400

        optimizer = CharteringOptimizer()
        result = optimizer.optimize(
            cargo_quantity=request.cargo_quantity,
            origin=request.origin,
            destination=request.destination,
            laycan_start=request.laycan_start,
            laycan_end=request.laycan_end,
            vessels_df=vessels_df,
            ports_df=ports_df,
            freight_forecast=forecast,
            current_freight_rate=request.current_freight_rate,
            contracts_df=contracts_df,
            port_congestion=avg_congestion,
            port_avg_delay=avg_delay,
            avg_bunker_price=bunker_avg,
            required_voyages=request.required_voyages
        )

        rec = Recommendation(
            cargo_id=1,
            action=result.recommended_action,
            vessel_id=result.recommended_vessel.get("id", 0),
            port_id=0,
            contract_type=result.recommended_contract,
            voyage_count=result.voyage_count,
            expected_cost_usd=result.expected_total_cost,
            cost_per_mt=result.cost_per_mt,
            risk_score=result.risk_score,
            confidence=result.confidence,
            expected_savings_usd=result.expected_savings,
            reasoning=json.dumps(result.reasoning),
            model_version="ensemble_v1"
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        return to_serializable({
            "recommendation_id": rec.id,
            "action": result.recommended_action,
            "vessel": result.recommended_vessel,
            "port": result.recommended_port,
            "contract_type": result.recommended_contract,
            "voyage_count": result.voyage_count,
            "expected_total_cost": result.expected_total_cost,
            "cost_per_mt": result.cost_per_mt,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "confidence": result.confidence,
            "expected_savings": result.expected_savings,
            "savings_pct": result.savings_pct,
            "all_options": result.all_options,
            "reasoning": result.reasoning,
            "feature_importance": result.feature_importance
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenario")
async def run_scenario(request: ScenarioRequest, db: Session = Depends(get_db)):
    try:
        vessels_df = load_vessels(db)
        ports_df = load_ports(db)
        contracts_df = load_contracts(db)

        base_forecast = {
            "forecast_value": request.base_params.current_freight_rate,
            "lower_bound": request.base_params.current_freight_rate * 0.85,
            "upper_bound": request.base_params.current_freight_rate * 1.15,
            "confidence": 0.75
        }

        base_params = {
            "cargo_quantity": request.base_params.cargo_quantity,
            "origin": request.base_params.origin,
            "destination": request.base_params.destination,
            "laycan_start": request.base_params.laycan_start,
            "laycan_end": request.base_params.laycan_end,
            "vessels_df": vessels_df,
            "ports_df": ports_df,
            "freight_forecast": base_forecast,
            "current_freight_rate": request.base_params.current_freight_rate,
            "contracts_df": contracts_df,
            "required_voyages": request.base_params.required_voyages
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
            "base_case": {
                "action": base_result.recommended_action,
                "total_cost": base_result.expected_total_cost,
                "risk_score": base_result.risk_score,
                "risk_level": base_result.risk_level,
                "contract_type": base_result.recommended_contract,
                "savings": base_result.expected_savings
            },
            "scenario": {
                "modifications": scenario_mods,
                "action": scenario_result["result"].recommended_action,
                "total_cost": scenario_result["result"].expected_total_cost,
                "risk_score": scenario_result["result"].risk_score,
                "risk_level": scenario_result["result"].risk_level,
                "contract_type": scenario_result["result"].recommended_contract,
                "savings": scenario_result["result"].expected_savings
            },
            "impact": {
                "cost_change": scenario_result["result"].expected_total_cost - base_result.expected_total_cost,
                "cost_change_pct": round(
                    (scenario_result["result"].expected_total_cost - base_result.expected_total_cost) /
                    base_result.expected_total_cost * 100, 1
                ) if base_result.expected_total_cost > 0 else 0,
                "recommendation_changed": base_result.recommended_action != scenario_result["result"].recommended_action
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/recommendation/{recommendation_id}")
async def get_recommendation(recommendation_id: int, db: Session = Depends(get_db)):
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    return {
        "id": rec.id,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "action": rec.action,
        "vessel_id": rec.vessel_id,
        "contract_type": rec.contract_type,
        "voyage_count": rec.voyage_count,
        "expected_cost_usd": rec.expected_cost_usd,
        "cost_per_mt": rec.cost_per_mt,
        "risk_score": rec.risk_score,
        "confidence": rec.confidence,
        "expected_savings_usd": rec.expected_savings_usd,
        "reasoning": json.loads(rec.reasoning) if rec.reasoning else [],
        "user_action": rec.user_action,
        "user_notes": rec.user_notes
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


@app.get("/api/vessels")
async def list_vessels(
    vessel_class: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    vessels_df = load_vessels(db, vessel_class=vessel_class)
    return {"vessels": vessels_df.to_dict(orient="records"), "count": len(vessels_df)}


@app.get("/api/ports")
async def list_ports(db: Session = Depends(get_db)):
    ports_df = load_ports(db)
    return {"ports": ports_df.to_dict(orient="records"), "count": len(ports_df)}


@app.get("/api/contracts")
async def list_contracts(db: Session = Depends(get_db)):
    contracts_df = load_contracts(db)
    return {"contracts": contracts_df.to_dict(orient="records"), "count": len(contracts_df)}


@app.get("/api/congestion")
async def get_congestion(
    port_name: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    congestion_df = load_congestion(db, port_name=port_name)
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


@app.post("/api/backtest")
async def run_backtest(
    route: str = Query(default="Australia-Paradip"),
    vessel_class: str = Query(default="panamax"),
    test_months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db)
):
    try:
        freight_df = load_freight_rates(db, route=route, vessel_class=vessel_class)
        commodity_df = load_commodity_prices(db)
        bunker_df = load_bunker_prices(db)

        featured_df = create_features(freight_df, commodity_df, bunker_df)

        forecaster = FreightForecaster()
        metrics = forecaster.backtest(featured_df, route, vessel_class, test_months)

        return {
            "route": route,
            "vessel_class": vessel_class,
            "test_months": test_months,
            "metrics": metrics
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
