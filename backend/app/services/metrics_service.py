"""
Metrics service — computes all KPIs from real stored data.
Never returns fabricated or hard-coded numbers.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recovery import RecoveryCase
from app.schemas.recovery import MetricsOverview


class MetricsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def compute_overview(self, simulation_run_id: str | None = None) -> MetricsOverview:
        from app.models.simulation import SimulationRun

        q = select(RecoveryCase)
        if simulation_run_id:
            # simulation_run_id may be either the short SIM-XXXXXXXX label or a full UUID
            resolved_uuid: uuid.UUID | None = None
            try:
                resolved_uuid = uuid.UUID(simulation_run_id)
            except (ValueError, AttributeError):
                # It's a short SIM-XXXXXXXX id — look up the DB UUID
                sim_result = await self._db.execute(
                    select(SimulationRun).where(SimulationRun.simulation_id == simulation_run_id)
                )
                sim = sim_result.scalar_one_or_none()
                if sim:
                    resolved_uuid = sim.id
            if resolved_uuid:
                q = q.where(RecoveryCase.simulation_run_id == resolved_uuid)

        result = await self._db.execute(q)
        cases = result.scalars().all()

        total = len(cases)
        recovered = sum(1 for c in cases if c.is_recovered)
        escalated = sum(1 for c in cases if c.status == "ESCALATED")
        active = sum(1 for c in cases if not c.is_stopped and not c.is_recovered)
        failed = sum(1 for c in cases if c.status == "FAILED")

        revenue_at_risk = sum(c.amount_at_risk_paise for c in cases)
        revenue_recovered = sum(c.amount_recovered_paise for c in cases if c.is_recovered)

        recovery_rate = (revenue_recovered / revenue_at_risk * 100) if revenue_at_risk > 0 else 0.0

        # Policy violations: count DENIED decisions where case still ran (should always be 0 by design)
        # Computed from actual policy_decision field on cases
        policy_violations = sum(1 for c in cases if c.policy_decision == "DENIED" and c.is_recovered)

        # By scenario
        scenarios = {}
        for scenario in ("FAILED_PAYMENT", "FAILED_SUBSCRIPTION", "CHECKOUT_ABANDONMENT"):
            sc = [c for c in cases if c.scenario == scenario]
            scenarios[scenario] = {
                "total": len(sc),
                "recovered": sum(1 for c in sc if c.is_recovered),
                "revenue_at_risk": sum(c.amount_at_risk_paise for c in sc),
                "revenue_recovered": sum(c.amount_recovered_paise for c in sc if c.is_recovered),
            }

        # By failure reason
        reasons = {}
        for c in cases:
            r = c.failure_reason
            if r not in reasons:
                reasons[r] = {"total": 0, "recovered": 0, "revenue_at_risk": 0, "revenue_recovered": 0}
            reasons[r]["total"] += 1
            reasons[r]["revenue_at_risk"] += c.amount_at_risk_paise
            if c.is_recovered:
                reasons[r]["recovered"] += 1
                reasons[r]["revenue_recovered"] += c.amount_recovered_paise

        return MetricsOverview(
            revenue_at_risk_paise=revenue_at_risk,
            revenue_recovered_paise=revenue_recovered,
            recovery_rate_pct=round(recovery_rate, 2),
            active_cases=active,
            escalated_cases=escalated,
            recovered_cases=recovered,
            failed_cases=failed,
            policy_violations=policy_violations,
            avg_recovery_time_hours=None,  # computed from audit timestamps in full impl
            total_cases=total,
            by_scenario=scenarios,
            by_failure_reason=reasons,
        )

    async def get_revenue_recovered(self, simulation_run_id: str | None = None) -> dict:
        overview = await self.compute_overview(simulation_run_id)
        return {
            "revenue_recovered_paise": overview.revenue_recovered_paise,
            "revenue_at_risk_paise": overview.revenue_at_risk_paise,
            "recovery_rate_pct": overview.recovery_rate_pct,
            "data_source": "SYNTHETIC_SIMULATION",
        }

    async def compare_runs(self, ai_run_id: str, baseline_run_id: str) -> dict:
        ai = await self.compute_overview(ai_run_id)
        baseline = await self.compute_overview(baseline_run_id)

        return {
            "REVENUERESCUE_AI": {
                "run_id": ai_run_id,
                "revenue_recovered_paise": ai.revenue_recovered_paise,
                "recovery_rate_pct": ai.recovery_rate_pct,
                "escalated_cases": ai.escalated_cases,
                "policy_violations": ai.policy_violations,
                "total_cases": ai.total_cases,
            },
            "BASELINE": {
                "run_id": baseline_run_id,
                "revenue_recovered_paise": baseline.revenue_recovered_paise,
                "recovery_rate_pct": baseline.recovery_rate_pct,
                "escalated_cases": baseline.escalated_cases,
                "policy_violations": baseline.policy_violations,
                "total_cases": baseline.total_cases,
            },
            "improvement_pct": round((ai.recovery_rate_pct - baseline.recovery_rate_pct), 2),
            "note": "All numbers computed from real simulation data — not fabricated",
        }
