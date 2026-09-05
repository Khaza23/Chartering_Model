from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import date
import pandas as pd


@dataclass
class FeasibleVessel:
    vessel_id: int
    name: str
    vessel_class: str
    capacity: float
    draft: float
    loa: float
    beam: float
    available_from: date
    available_until: date
    daily_hire_rate: float
    fuel_consumption: float
    speed_knots: float
    port_id: int
    port_name: str
    feasibility_score: float
    rejection_reasons: List[str]


class FeasibilityEngine:
    def __init__(self):
        self.hard_constraints = [
            "capacity_check",
            "draft_check",
            "loa_check",
            "beam_check",
            "laycan_check"
        ]

    def filter_vessels(self, vessels_df: pd.DataFrame, ports_df: pd.DataFrame,
                       cargo_quantity: float, laycan_start: date, laycan_end: date,
                       origin: str = None, destination: str = None) -> List[FeasibleVessel]:
        feasible = []

        for _, vessel in vessels_df.iterrows():
            for _, port in ports_df.iterrows():
                result = self._check_feasibility(vessel, port, cargo_quantity, laycan_start, laycan_end)
                if result["feasible"]:
                    feasible.append(result["vessel"])

        feasible.sort(key=lambda v: v.feasibility_score, reverse=True)
        return feasible

    def _check_feasibility(self, vessel: pd.Series, port: pd.Series,
                           cargo_quantity: float, laycan_start: date,
                           laycan_end: date) -> Dict:
        rejection_reasons = []
        passes = []

        if vessel["capacity"] < cargo_quantity:
            rejection_reasons.append(f"Capacity {vessel['capacity']:.0f} < required {cargo_quantity:.0f}")
        else:
            passes.append("capacity_check")

        if vessel["draft"] > port["draft_limit"]:
            rejection_reasons.append(f"Draft {vessel['draft']}m > port limit {port['draft_limit']}m")
        else:
            passes.append("draft_check")

        if vessel["loa"] > port["loa_limit"]:
            rejection_reasons.append(f"LOA {vessel['loa']}m > port limit {port['loa_limit']}m")
        else:
            passes.append("loa_check")

        if vessel["beam"] > port["beam_limit"]:
            rejection_reasons.append(f"Beam {vessel['beam']}m > port limit {port['beam_limit']}m")
        else:
            passes.append("beam_check")

        vessel_available_from = pd.to_datetime(vessel["available_from"]).date()
        vessel_available_until = pd.to_datetime(vessel["available_until"]).date()

        if vessel_available_from > laycan_end or vessel_available_until < laycan_start:
            rejection_reasons.append(
                f"Vessel available {vessel_available_from} to {vessel_available_until}, "
                f"but laycan is {laycan_start} to {laycan_end}"
            )
        else:
            passes.append("laycan_check")

        feasible = len(rejection_reasons) == 0

        feasibility_score = 0.0
        if feasible:
            capacity_utilization = cargo_quantity / vessel["capacity"]
            draft_margin = (port["draft_limit"] - vessel["draft"]) / port["draft_limit"]
            loa_margin = (port["loa_limit"] - vessel["loa"]) / port["loa_limit"]
            laycan_overlap = self._calculate_laycan_overlap(
                vessel_available_from, vessel_available_until, laycan_start, laycan_end
            )

            feasibility_score = (
                0.35 * min(capacity_utilization, 1.0) +
                0.25 * (1 - draft_margin) +
                0.20 * (1 - loa_margin) +
                0.20 * laycan_overlap
            )

            feasibility_score = max(0.0, min(1.0, feasibility_score))

        return {
            "feasible": feasible,
            "rejection_reasons": rejection_reasons,
            "vessel": FeasibleVessel(
                vessel_id=int(vessel["vessel_id"]),
                name=vessel["name"],
                vessel_class=vessel["vessel_class"],
                capacity=float(vessel["capacity"]),
                draft=float(vessel["draft"]),
                loa=float(vessel["loa"]),
                beam=float(vessel["beam"]),
                available_from=vessel_available_from,
                available_until=vessel_available_until,
                daily_hire_rate=float(vessel.get("daily_hire_rate", 15000)),
                fuel_consumption=float(vessel.get("fuel_consumption_tons_per_day", 35)),
                speed_knots=float(vessel.get("speed_knots", 13.5)),
                port_id=int(port["port_id"]),
                port_name=port["name"],
                feasibility_score=round(feasibility_score, 3),
                rejection_reasons=rejection_reasons
            ) if feasible else None
        }

    def _calculate_laycan_overlap(self, vessel_from, vessel_until, laycan_start, laycan_end):
        overlap_start = max(vessel_from, laycan_start)
        overlap_end = min(vessel_until, laycan_end)
        if overlap_start >= overlap_end:
            return 0.0
        overlap_days = (overlap_end - overlap_start).days
        total_days = (laycan_end - laycan_start).days
        if total_days == 0:
            return 0.0
        return min(overlap_days / total_days, 1.0)

    def score_port_feasibility(self, ports_df: pd.DataFrame, congestion_df: pd.DataFrame,
                               vessel: FeasibleVessel) -> List[Dict]:
        port_scores = []

        for _, port in ports_df.iterrows():
            port_congestion = congestion_df[congestion_df["port_name"] == port["name"]]

            if not port_congestion.empty:
                avg_congestion = port_congestion["congestion_index"].mean()
                avg_delay = port_congestion["expected_delay_hours"].mean()
                avg_waiting = port_congestion["vessels_waiting"].mean()
            else:
                avg_congestion = 30
                avg_delay = 12
                avg_waiting = 2

            draft_compat = 1 - abs(vessel.draft - port["draft_limit"] * 0.85) / port["draft_limit"]
            berth_score = min(port["berth_capacity"] / 10, 1.0)
            turnaround_score = max(0, 1 - port["avg_turnaround_hours"] / 120)
            congestion_score = max(0, 1 - avg_congestion / 100)
            handling_score = min(port["cargo_handling_rate"] / 5000, 1.0)

            overall = (
                0.25 * draft_compat +
                0.20 * berth_score +
                0.20 * turnaround_score +
                0.20 * congestion_score +
                0.15 * handling_score
            )

            port_scores.append({
                "port_id": int(port["port_id"]),
                "port_name": port["name"],
                "overall_score": round(overall, 3),
                "draft_compatibility": round(draft_compat, 3),
                "berth_availability": round(berth_score, 3),
                "turnaround": round(turnaround_score, 3),
                "congestion": round(congestion_score, 3),
                "handling_capacity": round(handling_score, 3),
                "avg_congestion_index": round(avg_congestion, 1),
                "avg_delay_hours": round(avg_delay, 1),
            })

        port_scores.sort(key=lambda x: x["overall_score"], reverse=True)
        return port_scores
