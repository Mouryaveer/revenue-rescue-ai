"""
Agent input/output schemas — validated with Pydantic on every LLM call.
The LLM must produce output matching DiagnosisOutput and StrategyOutput exactly.
Malformed output is rejected and triggers fallback — never executed.

NOTE: AgentState uses TypedDict (not Pydantic BaseModel) for LangGraph 0.2+ compatibility.
      LangGraph reserves some field names when using Pydantic models.
"""

from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict

from pydantic import BaseModel, Field, field_validator


class DiagnosisOutput(BaseModel):
    """Structured output from the diagnosis node. LLM-produced, Pydantic-validated."""

    diagnosis: str = Field(description="Short diagnosis label")
    diagnosis_confidence: float = Field(ge=0.0, le=1.0)
    failure_category: str = Field(description="Must match FailureReason enum")
    likely_cause: str = Field(description="Human-readable explanation — based on evidence only")
    is_recoverable: bool
    recommended_strategy: str = Field(description="Must match RecoveryStrategy enum")
    needs_human_review: bool = False
    notes: str = ""

    @field_validator("failure_category")
    @classmethod
    def validate_failure_category(cls, v: str) -> str:
        valid = {
            "INSUFFICIENT_FUNDS", "EXPIRED_METHOD", "GATEWAY_TEMPORARY",
            "BANK_DECLINE", "AUTH_FAILURE", "MANDATE_FAILURE",
            "SUBSCRIPTION_GRACE", "CHECKOUT_ABANDONED", "UNKNOWN",
        }
        if v not in valid:
            raise ValueError(f"Invalid failure_category: {v}. Must be one of {valid}")
        return v

    @field_validator("recommended_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid = {
            "RETRY_NOW", "SCHEDULE_RETRY", "PAYMENT_METHOD_UPDATE",
            "REMINDER", "CHECKOUT_RECOVERY", "PROMISE_TO_PAY", "ESCALATE",
        }
        if v not in valid:
            raise ValueError(f"Invalid strategy: {v}. Must be one of {valid}")
        return v


class StrategyOutput(BaseModel):
    """Structured output from the strategy node."""

    recovery_strategy: str = Field(description="Must match RecoveryStrategy enum")
    reason: str = Field(description="Why this strategy — based on evidence only")
    requested_action: dict = Field(description="Action spec: {type, delay_hours?, channel?}")
    expected_recovery_paise: int = Field(ge=0, description="Expected recovery in paise — heuristic only, never authoritative")
    confidence: float = Field(ge=0.0, le=1.0)
    fallback_strategy: Optional[str] = None

    @field_validator("recovery_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid = {
            "RETRY_NOW", "SCHEDULE_RETRY", "PAYMENT_METHOD_UPDATE",
            "REMINDER", "CHECKOUT_RECOVERY", "PROMISE_TO_PAY", "ESCALATE",
        }
        if v not in valid:
            raise ValueError(f"Invalid strategy: {v}")
        return v


class AgentState(TypedDict, total=False):
    """
    LangGraph state — TypedDict for full compatibility with LangGraph 0.2+.
    All fields optional (total=False) so partial updates work correctly.
    """

    # Identity (required at init)
    case_id: str
    agent_run_id: str

    # Event data
    event_type: str
    failure_reason: str
    amount_paise: int
    currency: str
    customer_id: str
    customer_segment: str
    customer_opted_out: bool
    customer_suspended: bool
    subscription_id: Optional[str]
    checkout_session_id: Optional[str]

    # Case state
    retry_count: int
    communication_count: int
    case_is_recovered: bool
    case_is_stopped: bool
    payment_already_succeeded: bool
    hours_since_last_attempt: Optional[float]
    checkout_timeout_elapsed: bool
    checkout_recovery_message_count: int

    # Node outputs
    case_diagnosis: Optional[DiagnosisOutput]   # renamed from 'diagnosis' to avoid LangGraph conflict
    case_strategy: Optional[StrategyOutput]      # renamed from 'strategy'
    policy_result: Optional[dict]
    execution_result: Optional[dict]
    verification_result: Optional[dict]

    # Control flow
    current_node: str
    error: Optional[str]
    escalation_reason: Optional[str]
    replan_count: int
    max_replans: int

    # Audit / tracing
    node_trace: list
    llm_provider: str


def make_initial_state(
    case_id: str,
    agent_run_id: str,
    event_type: str,
    failure_reason: str,
    amount_paise: int,
    customer_id: str,
    *,
    currency: str = "INR",
    customer_segment: str = "standard",
    customer_opted_out: bool = False,
    customer_suspended: bool = False,
    retry_count: int = 0,
    communication_count: int = 0,
    case_is_recovered: bool = False,
    payment_already_succeeded: bool = False,
    hours_since_last_attempt: Optional[float] = None,
    checkout_timeout_elapsed: bool = False,
    checkout_recovery_message_count: int = 0,
    llm_provider: str = "mock",
    subscription_id: Optional[str] = None,
    checkout_session_id: Optional[str] = None,
) -> AgentState:
    """Build the initial agent state with all required defaults."""
    return AgentState(
        case_id=case_id,
        agent_run_id=agent_run_id,
        event_type=event_type,
        failure_reason=failure_reason,
        amount_paise=amount_paise,
        currency=currency,
        customer_id=customer_id,
        customer_segment=customer_segment,
        customer_opted_out=customer_opted_out,
        customer_suspended=customer_suspended,
        subscription_id=subscription_id,
        checkout_session_id=checkout_session_id,
        retry_count=retry_count,
        communication_count=communication_count,
        case_is_recovered=case_is_recovered,
        case_is_stopped=False,
        payment_already_succeeded=payment_already_succeeded,
        hours_since_last_attempt=hours_since_last_attempt,
        checkout_timeout_elapsed=checkout_timeout_elapsed,
        checkout_recovery_message_count=checkout_recovery_message_count,
        case_diagnosis=None,
        case_strategy=None,
        policy_result=None,
        execution_result=None,
        verification_result=None,
        current_node="risk_detection",
        error=None,
        escalation_reason=None,
        replan_count=0,
        max_replans=3,
        node_trace=[],
        llm_provider=llm_provider,
    )
