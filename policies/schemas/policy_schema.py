"""
Policy schema — versioned, validated with Pydantic.
All policy evaluation is deterministic. Zero LLM involvement.
"""

from pydantic import BaseModel, Field


class RetryLimits(BaseModel):
    max_retries: int = Field(default=3, ge=0, le=10)
    max_auto_recovery_amount_paise: int = Field(default=5_000_000, ge=0)  # 50,000 INR in paise
    min_retry_interval_hours: int = Field(default=24, ge=0)


class CommunicationRules(BaseModel):
    respect_opt_out: bool = True
    max_messages_per_case: int = Field(default=3, ge=0, le=10)
    max_checkout_recovery_messages: int = Field(default=2, ge=0, le=5)


class CheckoutRules(BaseModel):
    abandonment_timeout_minutes: int = Field(default=30, ge=5, le=1440)
    max_recovery_messages: int = Field(default=2, ge=0, le=5)
    min_checkout_amount_paise: int = Field(default=10_000, ge=0)  # 100 INR in paise


class EscalationRules(BaseModel):
    after_failed_retries: int = Field(default=3, ge=1)
    high_value_threshold_paise: int = Field(default=5_000_000, ge=0)  # 50,000 INR
    unknown_failure: bool = True
    low_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class StoppingRules(BaseModel):
    stop_on_payment_success: bool = True
    stop_on_opt_out: bool = True
    stop_on_suspension: bool = True


class PolicyConfig(BaseModel):
    """
    Versioned merchant policy.
    This is the authoritative config that the PolicyEngine reads.
    The LLM never sees or modifies this config directly.
    """

    policy_id: str
    version: int = Field(ge=1)
    limits: RetryLimits = Field(default_factory=RetryLimits)
    communication: CommunicationRules = Field(default_factory=CommunicationRules)
    checkout: CheckoutRules = Field(default_factory=CheckoutRules)
    escalation: EscalationRules = Field(default_factory=EscalationRules)
    stopping: StoppingRules = Field(default_factory=StoppingRules)


class PolicyEvaluationResult(BaseModel):
    """
    Output of a single policy authorization check.
    Every result is recorded in the audit trail.
    """

    allowed: bool
    decision: str  # APPROVED | DENIED | ESCALATE | STOP
    reason: str
    policy_id: str
    policy_version: int
    violations: list[str] = Field(default_factory=list)
