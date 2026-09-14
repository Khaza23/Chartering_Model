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
    vessel_options: List[Dict] = field(default_factory=list)


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
        as_of: date = None,
    ) -> OptimizationResult:
        # as_of lets the timing advisor evaluate "what if we book later":
        # availability and laycan-slack math run against the simulated date.
        # Defaults to today so every existing caller is unaffected.
        _today = as_of or date.today()
        feasible_vessels = self.feasibility_engine.filter_vessels(
            vessels_df, ports_df, cargo_quantity, laycan_start, laycan_end, origin, destination
        )

        if not feasible_vessels:
            return self._no_feasible_solution()

        forecast_value = freight_forecast.get("forecast_value", current_freight_rate) if freight_forecast else current_freight_rate
        forecast_confidence = freight_forecast.get("confidence", 0.7) if freight_forecast else 0.7

        # Contract menu covers the requested program: only options that can
        # actually serve required_voyages voyages stay eligible.
        # Contract levels blend the user's observed rate (level anchor) with
        # the forecast (trend expectation) so the rate input visibly moves
        # the answer instead of being silently overridden by the model.
        _contract_base = (float(current_freight_rate) + float(forecast_value)) / 2.0
        contract_options = self._build_contract_options(
            _contract_base, contracts_df
        )
        try:
            _need_voyages = int(required_voyages or 1)
        except Exception:
            _need_voyages = 1

        laycan_days_away = (laycan_start - _today).days
        laycan_days_away = max(1, laycan_days_away)

        # Per-port congestion lookup from the FULL history (not destination-only)
        # so every vessel x port combo is costed/risked with its own port reality.
        port_congestion_map = self._build_port_congestion_map(
            congestion_df, port_congestion, port_avg_delay
        )

        # Evaluate EVERY feasible vessel x port combo on cost + risk,
        # instead of locking to feasible_vessels[0] before costing.
        all_triples = []  # (FeasibleVessel, contract_option)
        for fv in feasible_vessels:
            cong, delay = port_congestion_map.get(
                fv.port_name, (port_congestion, port_avg_delay)
            )
            comparison = self.cost_engine.compare_contract_costs(
                # Spot leg is priced at the user's observed market rate;
                # contract legs are priced off the forecast (future expectation).
                spot_rate=current_freight_rate,
                cargo_quantity=cargo_quantity,
                vessel=fv,
                port_name=fv.port_name,
                origin=origin,
                contract_options=contract_options,
                avg_bunker_price=avg_bunker_price,
                avg_congestion_index=cong
            )
            availability_days = (fv.available_until - _today).days
            # Program-basis savings: a multi-voyage total can only be judged
            # against N single spot voyages, not one. (The raw field from the
            # cost engine compares N voyages against 1, which is always deeply
            # negative and zeroes out the savings math downstream.)
            _spot_ref = next((o for o in comparison if o.get("type") == "spot"), None)
            if _spot_ref is not None:
                for o in comparison:
                    _prog_spot = _spot_ref["total_cost"] * int(o.get("voyages", 1))
                    o["savings_vs_spot"] = round(_prog_spot - o["total_cost"], 2)
                    o["savings_pct"] = round(
                        (o["savings_vs_spot"] / _prog_spot * 100) if _prog_spot > 0 else 0, 1
                    )
            comparison = self.risk_engine.calculate_risk_for_comparison(
                comparison,
                freight_forecast=freight_forecast,
                port_congestion=cong,
                port_avg_delay=delay,
                vessel_availability_days=availability_days,
                laycan_days_away=laycan_days_away
            )
            # A 1-voyage spot can't cover a multi-voyage program: drop options
            # below the requested voyage count (keep the largest as fallback).
            eligible = [o for o in comparison if int(o.get("voyages", 1)) >= _need_voyages]
            if not eligible:
                eligible = sorted(comparison, key=lambda o: int(o.get("voyages", 1)))[-1:]
            comparison = eligible
            for opt in comparison:
                opt["vessel_id"] = fv.vessel_id
                opt["vessel_name"] = fv.name
                opt["vessel_class"] = fv.vessel_class
                opt["port_name"] = fv.port_name
                opt["feasibility_score"] = fv.feasibility_score
                all_triples.append((fv, opt))

        if not all_triples:
            return self._no_feasible_solution()

        # The winner must discharge at the requested destination — other
        # ports stay visible as alternates (vessel_options) but can't win.
        dest_triples = [(fv, opt) for fv, opt in all_triples if fv.port_name == destination]
        if not dest_triples:
            return self._no_feasible_solution(
                f"No feasible vessel found that can serve {destination} "
                f"for {cargo_quantity:,.0f} MT in the laycan window"
            )

        # Winner across vessels AND contracts, within the destination port.
        best_vessel, best_option = self._select_best_triple(dest_triples, forecast_confidence)
        best_port_name = best_vessel.port_name

        # Contract comparison for the winning vessel x port (preserves existing UI).
        winning_comparison = [
            opt for fv, opt in all_triples
            if fv.vessel_id == best_vessel.vessel_id and fv.port_name == best_port_name
        ]

        # Ranked vessel x port shortlist (best contract per combo) for transparency.
        best_per_combo = {}
        for fv, opt in all_triples:
            key = (fv.vessel_id, fv.port_name)
            cur = best_per_combo.get(key)
            if cur is None or self._triple_score(
                [(fv, opt)], forecast_confidence, all_triples
            ) > self._triple_score([(cur[0], cur[1])], forecast_confidence, all_triples):
                best_per_combo[key] = (fv, opt)
        vessel_options = sorted(
            [
                {
                    "vessel_id": fv.vessel_id,
                    "vessel_name": fv.name,
                    "vessel_class": fv.vessel_class,
                    "port_name": fv.port_name,
                    "feasibility_score": fv.feasibility_score,
                    "type": opt["type"],
                    "voyages": opt["voyages"],
                    "total_cost": opt["total_cost"],
                    "cost_per_mt": opt["cost_per_mt"],
                    "risk_score": opt["risk_score"],
                    "risk_level": opt["risk_level"],
                }
                for fv, opt in best_per_combo.values()
            ],
            key=lambda o: o["total_cost"],
        )

        # Port ranking using the WINNER and full congestion history.
        try:
            _full_cong = congestion_df if congestion_df is not None and not congestion_df.empty else self._get_congestion_stub(destination)
        except Exception:
            _full_cong = self._get_congestion_stub(destination)
        port_scores = self.feasibility_engine.score_port_feasibility(
            ports_df, _full_cong, best_vessel
        )
        best_port = next(
            (p for p in port_scores if p["port_name"] == best_port_name),
            (port_scores[0] if port_scores else {"port_name": best_port_name}),
        )

        best_congestion, _best_delay = port_congestion_map.get(
            best_port_name, (port_congestion, port_avg_delay)
        )
        reasoning = self._generate_reasoning(
            best_option, winning_comparison, freight_forecast, best_congestion, best_vessel
        )

        feature_importance = self._compute_feature_importance(
            freight_forecast, best_congestion, best_vessel, best_option
        )

        # Program-basis savings live on the winning option itself (spot may be
        # legitimately absent from the comparison for multi-voyage programs).
        expected_savings = round(float(best_option.get("savings_vs_spot", 0) or 0), 2)
        savings_pct = round(float(best_option.get("savings_pct", 0) or 0), 1)

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
            expected_savings=expected_savings,
            savings_pct=savings_pct,
            all_options=winning_comparison,
            reasoning=reasoning,
            feature_importance=feature_importance,
            vessel_options=vessel_options
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

    def _build_port_congestion_map(self, congestion_df, fallback_congestion: float, fallback_delay: float) -> Dict:
        mapping = {}
        try:
            if congestion_df is not None and not congestion_df.empty:
                frame = congestion_df.tail(150)
                for port_name, grp in frame.groupby("port_name"):
                    try:
                        mapping[str(port_name)] = (
                            float(grp["congestion_index"].tail(30).mean()),
                            float(grp["expected_delay_hours"].tail(30).mean()),
                        )
                    except Exception:
                        continue
        except Exception:
            pass
        return mapping

    def _option_weights(self, confidence: float):
        if confidence > 0.8:
            return [0.45, 0.25, 0.30]
        elif confidence > 0.6:
            return [0.40, 0.35, 0.25]
        return [0.30, 0.45, 0.25]

    def _triple_score(self, triple, confidence: float, all_triples) -> float:
        _, opt = triple[0] if isinstance(triple, list) else triple
        all_opts = [o for _, o in all_triples]
        max_total = max(o["total_cost"] for o in all_opts) or 1
        max_sav = max((o.get("savings_vs_spot", 0) for o in all_opts), default=0)
        max_sav = max(max_sav, 1)
        cost_score = 1 - (opt["total_cost"] / max_total)
        risk_score = 1 - (opt["risk_score"] / 100)
        savings_score = opt.get("savings_vs_spot", 0) / max_sav
        w = self._option_weights(confidence)
        return w[0] * cost_score + w[1] * risk_score + w[2] * savings_score

    def _select_best_triple(self, all_triples, confidence: float):
        def _score(pair):
            _, opt = pair
            all_opts = [o for _, o in all_triples]
            max_total = max(o["total_cost"] for o in all_opts) or 1
            max_sav = max((o.get("savings_vs_spot", 0) for o in all_opts), default=0)
            max_sav = max(max_sav, 1)
            cost_score = 1 - (opt["total_cost"] / max_total)
            risk_score = 1 - (opt["risk_score"] / 100)
            savings_score = opt.get("savings_vs_spot", 0) / max_sav
            w = self._option_weights(confidence)
            return w[0] * cost_score + w[1] * risk_score + w[2] * savings_score

        return max(all_triples, key=_score)

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
                f"Vessel {vessel.name} ({vessel.vessel_class}) to {best_option.get('port_name', '')} "
                f"won on total cost (${best_option.get('total_cost', 0):,.0f}) with "
                f"feasibility score {vessel.feasibility_score:.2f}"
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

    def _no_feasible_solution(self, reason: str = "No feasible vessel-port combination found for the given constraints"):
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
            reasoning=[reason],
            feature_importance={},
            vessel_options=[]
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
