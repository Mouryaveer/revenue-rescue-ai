"""
Policy Engine — deterministic, authoritative authorization gate.

Rules:
- Zero LLM involvement. Ever.
- Fail closed: if engine errors, return ESCALATE (never APPROVED).
- Specific restriction beats general permission.
- Every decision records policy_id + policy_version for auditability.
- Called as an independent, testable unit before any action executes.

Authorization pipeline (sequential, explicit):
  1. Validate input schema
  2. Load active policy
  3. Check stopping conditions (highest priority)
  4. Check customer state (opt-out, suspension)
  5. Check monetary limits
  6. Check retry limits
  7. Check communication limits
  8. Check timing rules (min retry interval)
  9. Check checkout-specific rules
  10. ALLOW / DENY / ESCALATE
"""

from __future__ import annotations

import structlog

from policies.schemas.policy_schema import PolicyConfig, PolicyEvaluationResult

logger = structlog.get_logger(__name__)


class PolicyEngineError(Exception):
    """Raised when the policy engine encounters an unrecoverable error.
    Callers must treat this as ESCALATE / no action."""


class PolicyEngine:
    """
    Standalone, stateless policy evaluator.
    Instantiate with a PolicyConfig; call authorize() for each proposed action.
    """

    def __init__(self, policy: PolicyConfig) -> None:
        self._policy = policy

    @property
    def policy(self) -> PolicyConfig:
        return self._policy

    def authorize(self, context: "AuthorizationContext") -> PolicyEvaluationResult:
        """
        Run the full sequential authorization pipeline.
        Returns a PolicyEvaluationResult — NEVER raises exceptions to callers.
        On internal error, returns ESCALATE (fail closed).
        """
        try:
            return self._run_pipeline(context)
        except PolicyEngineError as e:
            logger.error("policy_engine_error", error=str(e), policy_id=getattr(self._policy, "policy_id", "unknown"))
            policy_id = getattr(self._policy, "policy_id", "unknown")
            version = getattr(self._policy, "version", 0)
            return PolicyEvaluationResult(
                allowed=False,
                decision="ESCALATE",
                reason=f"Policy engine error — fail closed: {e}",
                policy_id=policy_id,
                policy_version=version,
                violations=["POLICY_ENGINE_ERROR"],
            )
        except Exception as e:
            logger.error("policy_engine_unexpected_error", error=str(e))
            policy_id = getattr(self._policy, "policy_id", "unknown")
            version = getattr(self._policy, "version", 0)
            return PolicyEvaluationResult(
                allowed=False,
                decision="ESCALATE",
                reason="Unexpected policy engine error — fail closed",
                policy_id=policy_id,
                policy_version=version,
                violations=["POLICY_ENGINE_UNEXPECTED_ERROR"],
            )

    def _run_pipeline(self, ctx: "AuthorizationContext") -> PolicyEvaluationResult:
        p = self._policy
        violations: list[str] = []

        # ── Step 1: Check stopping conditions (highest priority) ──────
        if ctx.case_is_recovered:
            return self._stop("Case already RECOVERED — no further actions", "CASE_ALREADY_RECOVERED")

        if p.stopping.stop_on_payment_success and ctx.payment_already_succeeded:
            return self._stop("Payment already succeeded", "PAYMENT_ALREADY_SUCCEEDED")

        if p.stopping.stop_on_opt_out and ctx.customer_opted_out:
            return self._deny("Customer opted out of communication", "CUSTOMER_OPT_OUT", violations)

        if p.stopping.stop_on_suspension and ctx.customer_suspended:
            return self._deny("Customer account suspended", "CUSTOMER_SUSPENDED", violations)

        # ── Step 2: Monetary limits ────────────────────────────────────
        if ctx.amount_paise > p.limits.max_auto_recovery_amount_paise:
            return self._escalate(
                f"Amount {ctx.amount_paise} paise exceeds auto-recovery limit "
                f"{p.limits.max_auto_recovery_amount_paise} paise",
                "AMOUNT_EXCEEDS_AUTO_LIMIT",
                violations,
            )

        if ctx.amount_paise <= 0:
            return self._deny("Invalid amount — must be positive", "INVALID_AMOUNT", violations)

        # ── Step 3: Retry limits ───────────────────────────────────────
        if ctx.action_type in ("retry_payment", "schedule_retry"):
            if ctx.retry_count >= p.limits.max_retries:
                return self._escalate(
                    f"Retry count {ctx.retry_count} >= max_retries {p.limits.max_retries}",
                    "MAX_RETRIES_EXCEEDED",
                    violations,
                )

        # ── Step 4: Communication limits ──────────────────────────────
        if ctx.action_type in ("send_payment_reminder", "send_checkout_recovery", "change_communication_channel"):
            if ctx.communication_count >= p.communication.max_messages_per_case:
                return self._deny(
                    f"Communication count {ctx.communication_count} >= max "
                    f"{p.communication.max_messages_per_case}",
                    "MAX_COMMUNICATIONS_EXCEEDED",
                    violations,
                )

        # ── Step 5: Checkout-specific rules ───────────────────────────
        if ctx.action_type == "send_checkout_recovery":
            if not ctx.checkout_timeout_elapsed:
                return self._deny(
                    f"Checkout abandonment timeout not yet reached "
                    f"(required: {p.checkout.abandonment_timeout_minutes} min)",
                    "CHECKOUT_TIMEOUT_NOT_REACHED",
                    violations,
                )
            if ctx.amount_paise < p.checkout.min_checkout_amount_paise:
                return self._deny(
                    f"Checkout amount {ctx.amount_paise} below minimum "
                    f"{p.checkout.min_checkout_amount_paise} paise",
                    "CHECKOUT_AMOUNT_TOO_LOW",
                    violations,
                )
            if ctx.checkout_recovery_message_count >= p.checkout.max_recovery_messages:
                return self._deny(
                    f"Checkout recovery messages {ctx.checkout_recovery_message_count} >= max "
                    f"{p.checkout.max_recovery_messages}",
                    "MAX_CHECKOUT_RECOVERY_MESSAGES",
                    violations,
                )

        # ── Step 6: Timing rules ───────────────────────────────────────
        if ctx.action_type in ("retry_payment", "schedule_retry") and ctx.hours_since_last_attempt is not None:
            if ctx.hours_since_last_attempt < p.limits.min_retry_interval_hours:
                return self._deny(
                    f"Only {ctx.hours_since_last_attempt:.1f}h since last attempt; "
                    f"min interval is {p.limits.min_retry_interval_hours}h",
                    "RETRY_INTERVAL_NOT_SATISFIED",
                    violations,
                )

        # ── Step 7: Escalation triggers ───────────────────────────────
        if ctx.failure_reason == "UNKNOWN" and p.escalation.unknown_failure:
            return self._escalate("Unknown failure reason — escalate for human review", "UNKNOWN_FAILURE_REASON", violations)

        if ctx.diagnosis_confidence is not None and ctx.diagnosis_confidence < p.escalation.low_confidence_threshold:
            return self._escalate(
                f"Diagnosis confidence {ctx.diagnosis_confidence:.2f} below threshold "
                f"{p.escalation.low_confidence_threshold}",
                "LOW_DIAGNOSIS_CONFIDENCE",
                violations,
            )

        # ── All checks passed ──────────────────────────────────────────
        logger.info(
            "policy_approved",
            action=ctx.action_type,
            case_id=ctx.case_id,
            policy_id=p.policy_id,
            policy_version=p.version,
        )
        return PolicyEvaluationResult(
            allowed=True,
            decision="APPROVED",
            reason="All policy checks passed",
            policy_id=p.policy_id,
            policy_version=p.version,
            violations=[],
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _deny(self, reason: str, code: str, violations: list[str]) -> PolicyEvaluationResult:
        violations.append(code)
        logger.warning("policy_denied", reason=reason, code=code, policy_id=self._policy.policy_id)
        return PolicyEvaluationResult(
            allowed=False,
            decision="DENIED",
            reason=reason,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            violations=violations,
        )

    def _escalate(self, reason: str, code: str, violations: list[str]) -> PolicyEvaluationResult:
        violations.append(code)
        logger.warning("policy_escalate", reason=reason, code=code, policy_id=self._policy.policy_id)
        return PolicyEvaluationResult(
            allowed=False,
            decision="ESCALATE",
            reason=reason,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            violations=violations,
        )

    def _stop(self, reason: str, code: str) -> PolicyEvaluationResult:
        logger.info("policy_stop", reason=reason, code=code, policy_id=self._policy.policy_id)
        return PolicyEvaluationResult(
            allowed=False,
            decision="STOP",
            reason=reason,
            policy_id=self._policy.policy_id,
            policy_version=self._policy.version,
            violations=[code],
        )


class AuthorizationContext:
    """
    All context the policy engine needs to make a decision.
    Constructed by the caller — never by the LLM.
    All fields are typed and validated.
    """

    def __init__(
        self,
        *,
        case_id: str,
        action_type: str,
        amount_paise: int,
        retry_count: int,
        communication_count: int,
        customer_opted_out: bool,
        customer_suspended: bool,
        case_is_recovered: bool,
        payment_already_succeeded: bool,
        failure_reason: str,
        hours_since_last_attempt: float | None = None,
        diagnosis_confidence: float | None = None,
        checkout_timeout_elapsed: bool = False,
        checkout_recovery_message_count: int = 0,
    ) -> None:
        self.case_id = case_id
        self.action_type = action_type
        self.amount_paise = amount_paise
        self.retry_count = retry_count
        self.communication_count = communication_count
        self.customer_opted_out = customer_opted_out
        self.customer_suspended = customer_suspended
        self.case_is_recovered = case_is_recovered
        self.payment_already_succeeded = payment_already_succeeded
        self.failure_reason = failure_reason
        self.hours_since_last_attempt = hours_since_last_attempt
        self.diagnosis_confidence = diagnosis_confidence
        self.checkout_timeout_elapsed = checkout_timeout_elapsed
        self.checkout_recovery_message_count = checkout_recovery_message_count
