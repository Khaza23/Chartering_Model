from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import date, timedelta
import numpy as np


@dataclass
class CostBreakdown:
    vessel_id: int
    vessel_name: str
    port_id: int
    port_name: str
    route: str
    freight_cost: float
    bunker_cost: float
    port_charges: float
    loading_cost: float
    discharge_cost: float
    expected_demurrage: float
    expected_delay_cost: float
    other_costs: float
    total_cost: float
    cost_per_mt: float
    cargo_quantity: float
    voyage_days: float


class CostEngine:
    def __init__(self):
        self.port_charge_rates = {
            "Paradip": {"berth": 0.15, "handling": 2.5, "pilot": 0.5, "towage": 0.3},
            "Dhamra": {"berth": 0.12, "handling": 2.2, "pilot": 0.45, "towage": 0.28},
            "Gangavaram": {"berth": 0.14, "handling": 2.0, "pilot": 0.55, "towage": 0.32},
            "Vizag": {"berth": 0.16, "handling": 2.8, "pilot": 0.6, "towage": 0.35},
            "Mundra": {"berth": 0.13, "handling": 1.8, "pilot": 0.42, "towage": 0.25},
        }

    def calculate_total_cost(
        self,
        freight_rate_per_ton: float,
        cargo_quantity: float,
        vessel,
        port_name: str,
        origin: str,
        route_distance_nm: float = None,
        avg_bunker_price: float = 400.0,
        avg_congestion_index: float = 30.0,
        avg_delay_hours: float = 12.0
    ) -> CostBreakdown:
        def _get_vessel_attr(obj, attr, fallback=0.0):
            if hasattr(obj, 'get'):
                try:
                    v = obj.get(attr)
                    if v is not None and not (isinstance(v, float) and np.isnan(v)):
                        return v
                except Exception:
                    pass
            return getattr(obj, attr, fallback)

        freight_cost = freight_rate_per_ton * cargo_quantity

        if route_distance_nm is None:
            route_distance_nm = self._estimate_distance(origin, port_name)

        speed_knots = float(_get_vessel_attr(vessel, 'speed_knots', 14.0) or 14.0)
        fuel_consumption = float(
            _get_vessel_attr(vessel, 'fuel_consumption', None) or
            _get_vessel_attr(vessel, 'fuel_consumption_tons_per_day', 35.0) or
            35.0
        )
        daily_hire_rate = float(_get_vessel_attr(vessel, 'daily_hire_rate', 18000.0) or 18000.0)
        vessel_id = int(_get_vessel_attr(vessel, 'vessel_id', 0) or 0)
        vessel_name = str(_get_vessel_attr(vessel, 'name', 'Unknown') or 'Unknown')

        voyage_days = route_distance_nm / (speed_knots * 24)
        total_voyage_days = voyage_days * 2  # round trip assumption
        bunker_cost = (
            fuel_consumption * total_voyage_days * avg_bunker_price
        )

        port_rates = self.port_charge_rates.get(port_name, self.port_charge_rates["Paradip"])
        port_charges = (
            port_rates["berth"] * cargo_quantity +
            port_rates["handling"] * cargo_quantity / 1000 +
            port_rates["pilot"] * cargo_quantity / 1000 +
            port_rates["towage"] * cargo_quantity / 1000
        )

        loading_cost = 1.8 * cargo_quantity / 1000
        discharge_cost = 2.2 * cargo_quantity / 1000

        base_turnaround = 3  # days
        congestion_factor = 1 + (avg_congestion_index / 100) * 2
        expected_demurrage_days = max(0, (base_turnaround * congestion_factor) - base_turnaround)
        demurrage_rate = daily_hire_rate * 0.65
        expected_demurrage = expected_demurrage_days * demurrage_rate

        expected_delay_cost = (avg_delay_hours / 24) * daily_hire_rate * 0.5

        other_costs = (
            cargo_quantity * 0.5 + daily_hire_rate * 0.5
        )

        total_cost = (
            freight_cost + bunker_cost + port_charges + loading_cost +
            discharge_cost + expected_demurrage + expected_delay_cost + other_costs
        )

        cost_per_mt = total_cost / cargo_quantity if cargo_quantity > 0 else 0

        return CostBreakdown(
            vessel_id=vessel_id,
            vessel_name=vessel_name,
            port_id=0,
            port_name=port_name,
            route=f"{origin}-{port_name}",
            freight_cost=round(freight_cost, 2),
            bunker_cost=round(bunker_cost, 2),
            port_charges=round(port_charges, 2),
            loading_cost=round(loading_cost, 2),
            discharge_cost=round(discharge_cost, 2),
            expected_demurrage=round(expected_demurrage, 2),
            expected_delay_cost=round(expected_delay_cost, 2),
            other_costs=round(other_costs, 2),
            total_cost=round(total_cost, 2),
            cost_per_mt=round(cost_per_mt, 2),
            cargo_quantity=cargo_quantity,
            voyage_days=round(voyage_days, 1)
        )

    def compare_contract_costs(
        self,
        spot_rate: float,
        cargo_quantity: float,
        vessel,
        port_name: str,
        origin: str,
        contract_options: List[Dict],
        avg_bunker_price: float = 400.0,
        avg_congestion_index: float = 30.0
    ) -> List[Dict]:
        results = []

        spot_cost = self.calculate_total_cost(
            spot_rate, cargo_quantity, vessel, port_name, origin,
            avg_bunker_price=avg_bunker_price,
            avg_congestion_index=avg_congestion_index
        )

        results.append({
            "type": "spot",
            "voyages": 1,
            "freight_rate": spot_rate,
            "total_cost": spot_cost.total_cost,
            "cost_per_mt": spot_cost.cost_per_mt,
            "risk_level": "high",
            "savings_vs_spot": 0,
            "breakdown": spot_cost
        })

        for contract in contract_options:
            contract_rate = contract.get("freight_rate", spot_rate * 0.92)
            num_voyages = contract.get("voyages", 3)
            duration_months = contract.get("duration_months", num_voyages * 0.5)

            discount = 1.0 - (num_voyages * 0.012)
            effective_rate = contract_rate * discount

            voyage_costs = []
            for v in range(num_voyages):
                rate_drift = np.random.normal(0, 0.5) * (v / num_voyages)
                adjusted_rate = effective_rate + rate_drift
                voyage_cost = self.calculate_total_cost(
                    adjusted_rate, cargo_quantity, vessel, port_name, origin,
                    avg_bunker_price=avg_bunker_price * (1 + v * 0.01),
                    avg_congestion_index=avg_congestion_index
                )
                voyage_costs.append(voyage_cost)

            total_contract_cost = sum(vc.total_cost for vc in voyage_costs)
            avg_cost_per_mt = total_contract_cost / (cargo_quantity * num_voyages)

            risk_level = "low" if num_voyages >= 6 else "medium" if num_voyages >= 3 else "high"

            results.append({
                "type": contract.get("contract_type", "contract"),
                "voyages": num_voyages,
                "duration_months": duration_months,
                "freight_rate": round(effective_rate, 2),
                "total_cost": round(total_contract_cost, 2),
                "cost_per_mt": round(avg_cost_per_mt, 2),
                "risk_level": risk_level,
                "savings_vs_spot": round(spot_cost.total_cost - total_contract_cost, 2),
                "savings_pct": round(
                    ((spot_cost.total_cost - total_contract_cost) / spot_cost.total_cost) * 100, 1
                ),
                "voyage_breakdown": [
                    {
                        "voyage": i + 1,
                        "rate": round(vc.freight_cost / cargo_quantity, 2),
                        "total": round(vc.total_cost, 2)
                    } for i, vc in enumerate(voyage_costs)
                ]
            })

        return results

    def _estimate_distance(self, origin: str, destination: str) -> float:
        distances = {
            "Australia-Paradip": 5800,
            "Australia-Dhamra": 5900,
            "Australia-Gangavaram": 5700,
            "Australia-Vizag": 5650,
            "South Africa-Paradip": 7200,
            "Indonesia-Paradip": 3800,
            "Australia-Mundra": 6200,
            "Indonesia-Mundra": 3500,
        }
        key = f"{origin}-{destination}"
        return distances.get(key, 5500)
