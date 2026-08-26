"""
Recovery case request/response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RecoveryCaseSummary(BaseModel):
    id: str
    scenario: str
    failure_reason: str
    status: str
    amount_at_risk_paise: int
    amount_recovered_paise: int
    currency: str
    retry_count: int
    communication_count: int
    recovery_score: float | None
    customer_id: str
    is_recovered: bool
    is_stopped: bool
    created_at: datetime
    updated_at: datetime


class RecoveryCaseDetail(RecoveryCaseSummary):
    transaction_id: str | None
    subscription_id: str | None
    checkout_session_id: str | None
    diagnosis: dict | None
    strategy: dict | None
    policy_decision: str | None
    escalation_reason: str | None
    actions: list[dict]
    agent_runs: list[dict]


class AuditEventResponse(BaseModel):
    id: str
    event_type: str
    actor: str
    amount_paise: int | None
    policy_version: int | None
    result: str | None
    reason: str | None
    transaction_id: str | None
    created_at: datetime


class MetricsOverview(BaseModel):
    """
    All numbers computed from real stored data — never fabricated.
    Labeled SYNTHETIC_DATA in UI.
    """

    revenue_at_risk_paise: int
    revenue_recovered_paise: int
    recovery_rate_pct: float
    active_cases: int
    escalated_cases: int
    recovered_cases: int
    failed_cases: int
    policy_violations: int
    avg_recovery_time_hours: float | None
    total_cases: int
    # Breakdown by scenario
    by_scenario: dict[str, dict]
    # Breakdown by failure reason
    by_failure_reason: dict[str, dict]


class SimulationRunRequest(BaseModel):
    num_customers: int = 100
    num_events: int = 500
    failure_rate: float = 0.15
    random_seed: int = 42
    is_baseline: bool = False
    label: str = "Simulation Run"
    config: dict | None = None


class SimulationRunResponse(BaseModel):
    simulation_id: str
    status: str
    label: str
    is_baseline: bool
    num_events: int
    random_seed: int
    created_at: datetime
