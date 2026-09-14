"""Timing advisor: book now vs wait, without touching existing engines.

Re-runs the existing CharteringOptimizer once per wait date, simulating
"today + w" via optimize(..., as_of=...). Laycan stays fixed (waiting eats
slack and availability), bunker/congestion are held at current levels, and
rates follow the forecast curve. Verdict compares within one consistent set.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional

from .optimizer import CharteringOptimizer


@dataclass
class TimingVerdict:
    decision: str  # GO_NOW | WAIT | NO_FEASIBLE_WINDOW
    wait_days: int
    wait_date: Optional[str]
    expected_savings_vs_now: float
    savings_pct_vs_now: float
    confidence: float
    reasoning: List[str] = field(default_factory=list)


class TimingAdvisor:
    def __init__(self):
        self.optimizer = CharteringOptimizer()

    def advise(
        self,
        cargo_quantity: float,
        origin: str,
        destination: str,
        laycan_start: date,
        laycan_end: date,
        vessels_df=None,
        ports_df=None,
        contracts_df=None,
        forecast_curve: List[Dict] | None = None,
        base_current_rate: float = 22.0,
        base_freight_forecast: Dict | None = None,
        port_congestion: float = 30.0,
        port_avg_delay: float = 12.0,
        avg_bunker_price: float = 400.0,
        required_voyages: int = 6,
        congestion_df=None,
        wait_days: List[int] | None = None,
        base_today: date | None = None,
    ) -> Dict:
        today = base_today or date.today()
        waits = sorted({max(0, int(w)) for w in (wait_days or [0, 7, 14, 30, 45, 60])})
        curve = forecast_curve or []

        def _curve_at(w: int) -> Dict:
            if curve:
                pt = curve[min(w, len(curve) - 1)]
                return {
                    "forecast_value": float(pt.get("forecast_value", base_current_rate)),
                    "lower_bound": float(pt.get("lower_bound", base_current_rate * 0.85)),
                    "upper_bound": float(pt.get("upper_bound", base_current_rate * 1.15)),
                    "confidence": float(pt.get("confidence", 0.7)),
                }
            return {
                "forecast_value": base_current_rate,
                "lower_bound": base_current_rate * 0.85,
                "upper_bound": base_current_rate * 1.15,
                "confidence": 0.7,
            }

        options: List[Dict] = []
        for w in waits:
            sim_today = today + timedelta(days=w)
            if sim_today > laycan_end:
                options.append({
                    "wait_days": w,
                    "date": sim_today.isoformat(),
                    "feasible": False,
                    "reason": "Booking date falls after the laycan window closes",
                })
                continue
            if w == 0:
                rate_w = base_current_rate
                ff_w = base_freight_forecast or _curve_at(0)
            else:
                ff_w = _curve_at(w)
                rate_w = ff_w["forecast_value"]
            result = self.optimizer.optimize(
                cargo_quantity=cargo_quantity,
                origin=origin,
                destination=destination,
                laycan_start=laycan_start,
                laycan_end=laycan_end,
                vessels_df=vessels_df,
                ports_df=ports_df,
                freight_forecast=ff_w,
                current_freight_rate=rate_w,
                contracts_df=contracts_df,
                port_congestion=port_congestion,
                port_avg_delay=port_avg_delay,
                avg_bunker_price=avg_bunker_price,
                required_voyages=required_voyages,
                congestion_df=congestion_df,
                as_of=sim_today,
            )
            feasible = result.recommended_action != "NO_FEASIBLE_SOLUTION"
            # Horizon-decayed confidence: far-out forecasts earn less trust.
            decay = max(0.5, 1.0 - w / 120.0)
            options.append({
                "wait_days": w,
                "date": sim_today.isoformat(),
                "feasible": feasible,
                "action": result.recommended_action,
                "vessel": result.recommended_vessel,
                "port": result.recommended_port,
                "contract_type": result.recommended_contract,
                "voyage_count": result.voyage_count,
                "total_cost": result.expected_total_cost,
                "cost_per_mt": result.cost_per_mt,
                "risk_score": result.risk_score,
                "risk_level": result.risk_level,
                "confidence": round(result.confidence * decay, 2),
                "reason": (result.reasoning or [""])[0] if not feasible else None,
            })

        now_opts = [o for o in options if o["wait_days"] == 0 and o["feasible"]]
        now_total = now_opts[0]["total_cost"] if now_opts else None
        for o in options:
            if o["feasible"] and now_total:
                o["savings_vs_now"] = round(now_total - o["total_cost"], 2)
                o["savings_pct_vs_now"] = round(
                    (now_total - o["total_cost"]) / now_total * 100, 1
                )
            else:
                o["savings_vs_now"] = 0
                o["savings_pct_vs_now"] = 0.0

        feasible_opts = [o for o in options if o["feasible"]]
        verdict = self._build_verdict(feasible_opts, now_total, waits)

        return {
            "verdict": verdict,
            "options": options,
            "assumptions": [
                "Laycan window stays fixed — waiting consumes slack and vessel availability.",
                "Bunker price and port congestion are held at current levels for future dates.",
                "Future rates follow the freight forecast curve; confidence decays with horizon.",
            ],
        }

    def _build_verdict(self, feasible_opts: List[Dict], now_total, waits: List[int]) -> Dict:
        if not feasible_opts:
            return {
                "decision": "NO_FEASIBLE_WINDOW",
                "wait_days": 0,
                "wait_date": None,
                "expected_savings_vs_now": 0,
                "savings_pct_vs_now": 0.0,
                "confidence": 0,
                "reasoning": ["No feasible booking window found in the wait grid."],
            }
        best = min(feasible_opts, key=lambda o: o["total_cost"])
        reasoning = []
        trend_note = (
            "Market expected to fall — later dates price lower."
            if best["wait_days"] > 0
            else "No later date beats today's cost."
        )
        reasoning.append(trend_note)
        if best["wait_days"] > 0:
            reasoning.append(
                f"Waiting {best['wait_days']} days saves "
                f"${best['savings_vs_now']:,.0f} ({best['savings_pct_vs_now']:.1f}%) "
                f"vs booking now, at {best['confidence'] * 100:.0f}% confidence."
            )
            if best.get("vessel", {}).get("name"):
                reasoning.append(
                    f"Plan switches to {best['vessel']['name']} "
                    f"({best['vessel'].get('class', '')}) to {best['port']} "
                    f"on {best['contract_type'].replace('_', ' ')}."
                )
        else:
            reasoning.append("Booking now locks the lowest expected total cost.")
        return {
            "decision": "GO_NOW" if best["wait_days"] == 0 else "WAIT",
            "wait_days": best["wait_days"],
            "wait_date": best["date"],
            "expected_savings_vs_now": best["savings_vs_now"],
            "savings_pct_vs_now": best["savings_pct_vs_now"],
            "confidence": best["confidence"],
            "reasoning": reasoning,
        }
