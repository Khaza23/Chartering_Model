from dataclasses import dataclass
from typing import Dict, List
import numpy as np
import pandas as pd


@dataclass
class RiskScore:
    freight_risk: float
    port_risk: float
    vessel_risk: float
    contract_risk: float
    overall_risk: float
    risk_level: str
    freight_risk_factors: Dict
    port_risk_factors: Dict
    vessel_risk_factors: Dict
    contract_risk_factors: Dict


class RiskEngine:
    def __init__(self):
        self.freight_weight = 0.32
        self.port_weight = 0.21
        self.vessel_weight = 0.14
        self.contract_weight = 0.18
        self.market_weight = 0.15

    def calculate_risk(
        self,
        freight_forecast: Dict = None,
        port_congestion: float = 30.0,
        port_avg_delay: float = 12.0,
        vessel_availability_days: int = 60,
        laycan_days_away: int = 30,
        contract_type: str = "spot",
        voyage_count: int = 1,
        freight_volatility: float = 0.1,
        market_trend: float = 0.0
    ) -> RiskScore:
        freight_risk_factors = self._assess_freight_risk(
            freight_forecast, freight_volatility, market_trend
        )
        port_risk_factors = self._assess_port_risk(port_congestion, port_avg_delay)
        vessel_risk_factors = self._assess_vessel_risk(vessel_availability_days, laycan_days_away)
        contract_risk_factors = self._assess_contract_risk(contract_type, voyage_count)

        freight_score = freight_risk_factors["score"]
        port_score = port_risk_factors["score"]
        vessel_score = vessel_risk_factors["score"]
        contract_score = contract_risk_factors["score"]

        overall = (
            self.freight_weight * freight_score +
            self.port_weight * port_score +
            self.vessel_weight * vessel_score +
            self.contract_weight * contract_score
        )

        risk_level = self._classify_risk(overall)

        return RiskScore(
            freight_risk=round(freight_score, 1),
            port_risk=round(port_score, 1),
            vessel_risk=round(vessel_score, 1),
            contract_risk=round(contract_score, 1),
            overall_risk=round(overall, 1),
            risk_level=risk_level,
            freight_risk_factors=freight_risk_factors,
            port_risk_factors=port_risk_factors,
            vessel_risk_factors=vessel_risk_factors,
            contract_risk_factors=contract_risk_factors
        )

    def _assess_freight_risk(self, forecast: Dict, volatility: float, trend: float) -> Dict:
        score = 50
        factors = {}

        if forecast:
            confidence = forecast.get("confidence", 0.7)
            uncertainty = forecast.get("upper_bound", 0) - forecast.get("lower_bound", 0)
            forecast_val = forecast.get("forecast_value", 0)

            uncertainty_ratio = uncertainty / forecast_val if forecast_val > 0 else 0
            uncertainty_risk = min(uncertainty_ratio * 200, 40)
            score += uncertainty_risk - (1 - confidence) * 30
            factors["forecast_uncertainty"] = round(uncertainty_ratio * 100, 1)

        vol_risk = min(volatility * 200, 30)
        score += vol_risk - 10
        factors["volatility"] = round(volatility * 100, 1)

        trend_risk = abs(trend) * 100
        score += trend_risk * 0.3
        factors["trend_momentum"] = round(trend * 100, 1)

        score = max(0, min(100, score))
        return {"score": score, "factors": factors}

    def _assess_port_risk(self, congestion: float, avg_delay: float) -> Dict:
        score = 20
        factors = {}

        congestion_risk = congestion * 0.4
        score += congestion_risk
        factors["congestion_index"] = round(congestion, 1)

        delay_risk = min(avg_delay / 2, 25)
        score += delay_risk
        factors["avg_delay_hours"] = round(avg_delay, 1)

        if congestion > 70:
            score += 10
            factors["congestion_alert"] = "HIGH"
        elif congestion > 50:
            score += 5
            factors["congestion_alert"] = "MEDIUM"
        else:
            factors["congestion_alert"] = "LOW"

        score = max(0, min(100, score))
        return {"score": score, "factors": factors}

    def _assess_vessel_risk(self, availability_days: int, laycan_days_away: int) -> Dict:
        score = 10
        factors = {}

        margin = availability_days - laycan_days_away
        if margin < 5:
            score += 40
            factors["availability_margin"] = "CRITICAL"
        elif margin < 15:
            score += 20
            factors["availability_margin"] = "TIGHT"
        elif margin < 30:
            score += 10
            factors["availability_margin"] = "ADEQUATE"
        else:
            factors["availability_margin"] = "COMFORTABLE"

        factors["margin_days"] = margin
        score = max(0, min(100, score))
        return {"score": score, "factors": factors}

    def _assess_contract_risk(self, contract_type: str, voyage_count: int) -> Dict:
        base_risk = {
            "spot": 60,
            "short_term": 35,
            "medium_term": 25
        }
        score = base_risk.get(contract_type, 50)
        factors = {"contract_type": contract_type, "voyage_count": voyage_count}

        if voyage_count > 8:
            score += 10
            factors["commitment_risk"] = "HIGH"
        elif voyage_count > 4:
            factors["commitment_risk"] = "MEDIUM"
        else:
            factors["commitment_risk"] = "LOW"

        score = max(0, min(100, score))
        return {"score": score, "factors": factors}

    def _classify_risk(self, score: float) -> str:
        if score < 30:
            return "LOW"
        elif score < 55:
            return "MEDIUM"
        elif score < 75:
            return "HIGH"
        else:
            return "VERY_HIGH"

    def calculate_risk_for_comparison(
        self,
        comparison_results: List[Dict],
        freight_forecast: Dict = None,
        port_congestion: float = 30.0,
        port_avg_delay: float = 12.0,
        vessel_availability_days: int = 60,
        laycan_days_away: int = 30
    ) -> List[Dict]:
        for option in comparison_results:
            risk = self.calculate_risk(
                freight_forecast=freight_forecast,
                port_congestion=port_congestion,
                port_avg_delay=port_avg_delay,
                vessel_availability_days=vessel_availability_days,
                laycan_days_away=laycan_days_away,
                contract_type=option["type"],
                voyage_count=option["voyages"]
            )
            option["risk_score"] = risk.overall_risk
            option["risk_level"] = risk.risk_level
            option["risk_breakdown"] = {
                "freight": risk.freight_risk,
                "port": risk.port_risk,
                "vessel": risk.vessel_risk,
                "contract": risk.contract_risk
            }

        return comparison_results
