from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import date
import numpy as np
from .feasibility import FeasibilityEngine, FeasibleVessel
from .cost_engine import CostEngine, CostBreakdown
from risk.risk_engine import RiskEngine, RiskScore


@dataclass
class OptimizationResult:
    recommended_action: str
    recommended_vessel: Dict
    recommended_port: str
    recommended_contract: str
    voyage_count: int
    expected_total_cost: float
    cost_per_mt: float
    risk_score: float
    risk_level: str
    confidence: float
    expected_savings: float
    savings_pct: float
    all_options: List[Dict]
    reasoning: List[str]
    feature_importance: Dict


class CharteringOptimizer:
    def __init__(self):
        self.feasibility_engine = FeasibilityEngine()
        self.cost_engine = CostEngine()
        self.risk_engine = RiskEngine()

    def optimize(
        self,
        cargo_quantity: float,
        origin: str,
        destination: str,
        laycan_start: date,
        laycan_end: date,
        vessels_df=None,
        ports_df=None,
        freight_forecast: Dict = None,
        current_freight_rate: float = 22.0,
        contracts_df=None,
        port_congestion: float = 30.0,
        port_avg_delay: float = 12.0,
        avg_bunker_price: float = 400.0,
        required_voyages: int = 6,
        congestion_df=None,
    ) -> OptimizationResult:
        feasible_vessels = self.feasibility_engine.filter_vessels(
            vessels_df, ports_df, cargo_quantity, laycan_start, laycan_end, origin, destination
        )

        if not feasible_vessels:
            return self._no_feasible_solution()

        # Reconfigure: prefer real congestion history (incl. live/aisstream rows)
        # for the destination; fall back to stub only when empty/missing.
        _congestion_frame = congestion_df
        try:
            if _congestion_frame is not None and not _congestion_frame.empty:
                _dest = _congestion_frame[_congestion_frame["port_name"] == destination]
                if _dest.empty:
                    _congestion_frame = self._get_congestion_stub(destination)
                else:
                    _congestion_frame = _dest.tail(30)
            else:
                _congestion_frame = self._get_congestion_stub(destination)
        except Exception:
            _congestion_frame = self._get_congestion_stub(destination)

        port_scores = self.feasibility_engine.score_port_feasibility(
            ports_df, _congestion_frame, feasible_vessels[0]
        )

        best_vessel = feasible_vessels[0]
        best_port = port_scores[0] if port_scores else {"port_name": destination}

        forecast_value = freight_forecast.get("forecast_value", current_freight_rate) if freight_forecast else current_freight_rate
        forecast_confidence = freight_forecast.get("confidence", 0.7) if freight_forecast else 0.7

        contract_options = self._build_contract_options(
            forecast_value, contracts_df
        )

        comparison = self.cost_engine.compare_contract_costs(
            spot_rate=forecast_value,
            cargo_quantity=cargo_quantity,
            vessel=best_vessel,
            port_name=best_port["port_name"],
            origin=origin,
            contract_options=contract_options,
            avg_bunker_price=avg_bunker_price,
            avg_congestion_index=port_congestion
        )

        laycan_days_away = (laycan_start - date.today()).days
        laycan_days_away = max(1, laycan_days_away)

        availability_days = (best_vessel.available_until - date.today()).days

        comparison = self.risk_engine.calculate_risk_for_comparison(
            comparison,
            freight_forecast=freight_forecast,
            port_congestion=port_congestion,
            port_avg_delay=port_avg_delay,
            vessel_availability_days=availability_days,
            laycan_days_away=laycan_days_away
        )

        best_option = self._select_best_option(comparison, forecast_confidence)

        reasoning = self._generate_reasoning(
            best_option, comparison, freight_forecast, port_congestion, best_vessel
        )

        feature_importance = self._compute_feature_importance(
            freight_forecast, port_congestion, best_vessel, best_option
        )

        spot_cost = next((c for c in comparison if c["type"] == "spot"), None)
        expected_savings = spot_cost["total_cost"] - best_option["total_cost"] if spot_cost else 0
        savings_pct = (expected_savings / spot_cost["total_cost"] * 100) if spot_cost and spot_cost["total_cost"] > 0 else 0

        return OptimizationResult(
            recommended_action=self._map_action(best_option["type"]),
            recommended_vessel={
                "id": best_vessel.vessel_id,
                "name": best_vessel.name,
                "class": best_vessel.vessel_class,
                "capacity": best_vessel.capacity,
                "port_name": best_port["port_name"]
            },
            recommended_port=best_port["port_name"],
            recommended_contract=best_option["type"],
            voyage_count=best_option["voyages"],
            expected_total_cost=best_option["total_cost"],
            cost_per_mt=best_option["cost_per_mt"],
            risk_score=best_option["risk_score"],
            risk_level=best_option["risk_level"],
            confidence=forecast_confidence,
            expected_savings=round(expected_savings, 2),
            savings_pct=round(savings_pct, 1),
            all_options=comparison,
            reasoning=reasoning,
            feature_importance=feature_importance
        )

    def _build_contract_options(self, current_rate: float, contracts_df=None):
        options = [
            {"contract_type": "short_term", "freight_rate": current_rate * 0.97, "voyages": 3, "duration_months": 2},
            {"contract_type": "medium_term", "freight_rate": current_rate * 0.94, "voyages": 6, "duration_months": 4},
            {"contract_type": "medium_term", "freight_rate": current_rate * 0.91, "voyages": 12, "duration_months": 8},
        ]

        if contracts_df is not None and not contracts_df.empty:
            for _, row in contracts_df.iterrows():
                if row.get("contract_type") != "spot":
                    options.append({
                        "contract_type": row["contract_type"],
                        "freight_rate": row.get("freight_rate", current_rate * 0.95),
                        "voyages": row.get("voyages", 3),
                        "duration_months": row.get("duration_months", 3)
                    })

        return options

    def _select_best_option(self, comparison: List[Dict], confidence: float) -> Dict:
        def score_option(opt):
            cost_score = 1 - (opt["total_cost"] / max(c["total_cost"] for c in comparison))
            risk_score = 1 - (opt["risk_score"] / 100)
            savings_score = opt.get("savings_vs_spot", 0) / max(
                max(c.get("savings_vs_spot", 0) for c in comparison), 1
            )

            if confidence > 0.8:
                weights = [0.45, 0.25, 0.30]
            elif confidence > 0.6:
                weights = [0.40, 0.35, 0.25]
            else:
                weights = [0.30, 0.45, 0.25]

            return weights[0] * cost_score + weights[1] * risk_score + weights[2] * savings_score

        return max(comparison, key=score_option)

    def _map_action(self, contract_type: str) -> str:
        mapping = {
            "spot": "BOOK_NOW",
            "short_term": "SHORT_CONTRACT",
            "medium_term": "MEDIUM_CONTRACT"
        }
        return mapping.get(contract_type, "WAIT")

    def _generate_reasoning(self, best_option, comparison, forecast, congestion, vessel):
        reasons = []

        if forecast:
            trend = forecast.get("trend", "stable")
            if trend == "rising":
                reasons.append("Freight market expected to rise - locking in contract rate advantageous")
            elif trend == "falling":
                reasons.append("Freight market expected to fall - spot market may offer better rates")
            else:
                reasons.append("Freight market relatively stable - contract provides cost certainty")

        if best_option["risk_level"] == "LOW":
            reasons.append("Risk profile is LOW - favorable conditions for commitment")
        elif best_option["risk_level"] == "MEDIUM":
            reasons.append("Risk profile is MEDIUM - balanced approach recommended")
        else:
            reasons.append("Risk profile is HIGH - caution advised")

        if best_option.get("savings_vs_spot", 0) > 0:
            reasons.append(
                f"Expected savings of ${best_option['savings_vs_spot']:,.0f} vs spot "
                f"({best_option.get('savings_pct', 0):.1f}%)"
            )

        if congestion > 50:
            reasons.append("Port congestion elevated - may impact scheduling")

        if vessel:
            reasons.append(
                f"Vessel {vessel.name} ({vessel.vessel_class}) fits port constraints "
                f"with feasibility score {vessel.feasibility_score:.2f}"
            )

        if best_option["voyages"] >= 6:
            reasons.append(
                f"Multi-voyage commitment ({best_option['voyages']} voyages) provides "
                f"volume discount and scheduling certainty"
            )

        return reasons

    def _compute_feature_importance(self, forecast, congestion, vessel, best_option):
        importance = {
            "freight_trend": 30,
            "contract_discount": 22,
            "port_congestion": 18,
            "vessel_availability": 12,
            "bunker_price": 10,
            "laycan_flexibility": 8
        }

        if forecast and forecast.get("confidence", 0) < 0.6:
            importance["freight_trend"] = 20
            importance["vessel_availability"] = 18

        if congestion > 60:
            importance["port_congestion"] = 28
            importance["freight_trend"] = 22

        total = sum(importance.values())
        return {k: round(v / total * 100, 1) for k, v in importance.items()}

    def _no_feasible_solution(self):
        return OptimizationResult(
            recommended_action="NO_FEASIBLE_SOLUTION",
            recommended_vessel={},
            recommended_port="",
            recommended_contract="",
            voyage_count=0,
            expected_total_cost=0,
            cost_per_mt=0,
            risk_score=100,
            risk_level="VERY_HIGH",
            confidence=0,
            expected_savings=0,
            savings_pct=0,
            all_options=[],
            reasoning=["No feasible vessel-port combination found for the given constraints"],
            feature_importance={}
        )

    def _get_congestion_stub(self, port_name):
        import pandas as pd
        return pd.DataFrame({
            "port_name": [port_name],
            "congestion_index": [30],
            "expected_delay_hours": [12],
            "vessels_waiting": [2]
        })

    def run_scenario(self, base_params: Dict, scenario_modifications: Dict) -> Dict:
        modified_params = {**base_params}

        if "freight_change_pct" in scenario_modifications:
            mod = scenario_modifications["freight_change_pct"]
            if base_params.get("freight_forecast"):
                factor = 1 + mod / 100
                modified_params["freight_forecast"] = {
                    **base_params["freight_forecast"],
                    "forecast_value": base_params["freight_forecast"]["forecast_value"] * factor,
                    "lower_bound": base_params["freight_forecast"]["lower_bound"] * factor,
                    "upper_bound": base_params["freight_forecast"]["upper_bound"] * factor
                }
            modified_params["current_freight_rate"] = base_params.get("current_freight_rate", 22) * (1 + mod / 100)

        if "bunker_change_pct" in scenario_modifications:
            mod = scenario_modifications["bunker_change_pct"]
            modified_params["avg_bunker_price"] = base_params.get("avg_bunker_price", 400) * (1 + mod / 100)

        if "congestion_change" in scenario_modifications:
            modified_params["port_congestion"] = base_params.get("port_congestion", 30) + scenario_modifications["congestion_change"]

        if "delay_change_hours" in scenario_modifications:
            modified_params["port_avg_delay"] = base_params.get("port_avg_delay", 12) + scenario_modifications["delay_change_hours"]

        result = self.optimize(**modified_params)
        return {
            "scenario": scenario_modifications,
            "result": result
        }
