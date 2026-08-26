"""
Recovery tool definitions.
These are PROPOSAL schemas only — the LLM can reference them by name.
Actual execution ONLY happens through the Action Executor after Policy Engine approval.
No tool here directly calls execute_payment(), send_message(), etc.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Tool input schemas ─────────────────────────────────────────────────────────


class RetryPaymentInput(BaseModel):
    """Propose an immediate payment retry."""

    case_id: str
    reason: str = Field(description="Why retry now — evidence-based only")


class ScheduleRetryInput(BaseModel):
    """Propose a scheduled payment retry after a delay."""

    case_id: str
    delay_hours: int = Field(ge=1, le=168, description="Hours to wait before retry")
    reason: str


class SendPaymentReminderInput(BaseModel):
    """Propose sending a payment reminder communication."""

    case_id: str
    channel: str = Field(default="email", description="email | sms | push")
    reason: str


class RequestPaymentMethodUpdateInput(BaseModel):
    """Propose requesting customer to update payment method."""

    case_id: str
    reason: str


class ChangeChannelInput(BaseModel):
    """Propose switching communication channel."""

    case_id: str
    from_channel: str
    to_channel: str
    reason: str


class CreatePromiseToPayInput(BaseModel):
    """Propose recording a customer's promise to pay."""

    case_id: str
    promised_date: str = Field(description="ISO date string")
    amount_paise: int
    reason: str


class SendCheckoutRecoveryInput(BaseModel):
    """
    Propose sending a checkout recovery message.
    CHECKOUT_ABANDONMENT scenario only.
    Simulated communication — no real SMS/email/WhatsApp sent.
    """

    case_id: str
    checkout_session_id: str
    channel: str = Field(default="email", description="email | sms | push")
    reason: str


class EscalateToHumanInput(BaseModel):
    """Propose escalating case to human operator."""

    case_id: str
    reason: str
    urgency: str = Field(default="normal", description="normal | high | critical")


class StopRecoveryInput(BaseModel):
    """Propose stopping all recovery actions on this case."""

    case_id: str
    reason: str


# ── Tool registry ──────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, type[BaseModel]] = {
    "retry_payment": RetryPaymentInput,
    "schedule_retry": ScheduleRetryInput,
    "send_payment_reminder": SendPaymentReminderInput,
    "request_payment_method_update": RequestPaymentMethodUpdateInput,
    "change_communication_channel": ChangeChannelInput,
    "create_promise_to_pay": CreatePromiseToPayInput,
    "send_checkout_recovery": SendCheckoutRecoveryInput,
    "escalate_to_human": EscalateToHumanInput,
    "stop_recovery": StopRecoveryInput,
}


def validate_tool_call(tool_name: str, payload: dict) -> BaseModel:
    """
    Validate a proposed tool call against its schema.
    Raises ValidationError if invalid — call is rejected, never executed.
    """
    schema = TOOL_REGISTRY.get(tool_name)
    if not schema:
        raise ValueError(f"Unknown tool: {tool_name}. Available: {list(TOOL_REGISTRY)}")
    return schema(**payload)
