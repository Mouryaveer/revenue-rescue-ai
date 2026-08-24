"""
Recovery models: RecoveryCase, RecoveryAction, AgentRun, AgentDecision, Escalation.
"""

import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel
from app.models.enums import (
    FailureReason,
    PolicyDecision,
    RecoveryCaseStatus,
    RecoveryScenario,
    RecoveryStrategy,
)


class RecoveryCase(TimestampedModel):
    __tablename__ = "recovery_cases"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    checkout_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("checkout_sessions.id"), nullable=True)
    simulation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=True)

    scenario: Mapped[RecoveryScenario] = mapped_column(String(50), nullable=False)
    failure_reason: Mapped[FailureReason] = mapped_column(String(50), nullable=False)
    status: Mapped[RecoveryCaseStatus] = mapped_column(String(30), nullable=False, default=RecoveryCaseStatus.DETECTED)

    amount_at_risk_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_recovered_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    communication_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Recovery score (0–100)
    recovery_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # AI diagnosis / strategy (stored as JSONB — never execute from here directly)
    diagnosis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    strategy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    policy_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Idempotency — once RECOVERED, no further actions
    is_recovered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_stopped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source event idempotency key
    source_event_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="recovery_cases")
    actions: Mapped[list["RecoveryAction"]] = relationship("RecoveryAction", back_populates="recovery_case")
    agent_runs: Mapped[list["AgentRun"]] = relationship("AgentRun", back_populates="recovery_case")
    audit_events: Mapped[list["AuditEvent"]] = relationship("AuditEvent", back_populates="recovery_case")
    escalations: Mapped[list["Escalation"]] = relationship("Escalation", back_populates="recovery_case")
    escalations: Mapped[list["Escalation"]] = relationship("Escalation", back_populates="recovery_case")


class RecoveryAction(TimestampedModel):
    __tablename__ = "recovery_actions"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True)

    action_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. retry_payment
    strategy_code: Mapped[RecoveryStrategy] = mapped_column(String(50), nullable=False)
    policy_decision: Mapped[PolicyDecision] = mapped_column(String(30), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Execution
    was_executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_result: Mapped[str | None] = mapped_column(String(50), nullable=True)  # SUCCESS/FAILED
    result_transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount_recovered_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Idempotency key for this specific action
    action_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    input_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    denial_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    recovery_case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="actions")
    agent_run: Mapped["AgentRun | None"] = relationship("AgentRun", back_populates="actions")


class AgentRun(TimestampedModel):
    __tablename__ = "agent_runs"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False, index=True)

    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai / mock
    run_status: Mapped[str] = mapped_column(String(30), nullable=False, default="RUNNING")
    node_trace: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ordered list of nodes visited
    llm_input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    recovery_case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="agent_runs")
    actions: Mapped[list["RecoveryAction"]] = relationship("RecoveryAction", back_populates="agent_run")
    decisions: Mapped[list["AgentDecision"]] = relationship("AgentDecision", back_populates="agent_run")


class AgentDecision(TimestampedModel):
    __tablename__ = "agent_decisions"

    agent_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True)
    recovery_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False)

    node: Mapped[str] = mapped_column(String(100), nullable=False)
    decision_type: Mapped[str] = mapped_column(String(100), nullable=False)
    input_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    agent_run: Mapped["AgentRun"] = relationship("AgentRun", back_populates="decisions")


class Escalation(TimestampedModel):
    __tablename__ = "escalations"

    recovery_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=False, index=True)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    context_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    recovery_case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="escalations")
