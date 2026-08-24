"""
Pre-built scenarios for the 5-minute demo.
Each scenario is deterministic — seeded RNG, same output every run.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DemoScenario:
    name: str
    event_type: str
    failure_reason: str
    amount_paise: int
    customer_segment: str
    seed: int
    expected_outcome: str  # RECOVERED | ESCALATED | STOPPED | FAILED
    demo_note: str


DEMO_SCENARIOS: list[DemoScenario] = [
    DemoScenario(
        name="gateway_quick_recovery",
        event_type="FAILED_PAYMENT",
        failure_reason="GATEWAY_TEMPORARY",
        amount_paise=199900,
        customer_segment="premium",
        seed=7,
        expected_outcome="RECOVERED",
        demo_note="Retry #1 succeeds — clean recovery path for the demo",
    ),
    DemoScenario(
        name="insufficient_funds_delayed",
        event_type="FAILED_PAYMENT",
        failure_reason="INSUFFICIENT_FUNDS",
        amount_paise=499900,
        customer_segment="standard",
        seed=42,
        expected_outcome="RECOVERED",
        demo_note="Retry after 24h — demonstrates scheduled retry flow",
    ),
    DemoScenario(
        name="checkout_abandonment_recovered",
        event_type="CHECKOUT_ABANDONMENT",
        failure_reason="CHECKOUT_ABANDONED",
        amount_paise=349900,
        customer_segment="premium",
        seed=15,
        expected_outcome="RECOVERED",
        demo_note="Recovery message → customer resumes → payment succeeds",
    ),
    DemoScenario(
        name="4th_retry_policy_denied",
        event_type="FAILED_PAYMENT",
        failure_reason="INSUFFICIENT_FUNDS",
        amount_paise=299900,
        customer_segment="standard",
        seed=42,
        expected_outcome="ESCALATED",
        demo_note="RED-TEAM: retry_count=3 → PolicyEngine DENIES → not executed",
    ),
    DemoScenario(
        name="opted_out_communication_blocked",
        event_type="FAILED_PAYMENT",
        failure_reason="BANK_DECLINE",
        amount_paise=149900,
        customer_segment="at_risk",
        seed=42,
        expected_outcome="STOPPED",
        demo_note="RED-TEAM: customer opted out → DENIED by policy",
    ),
    DemoScenario(
        name="high_value_auto_escalation",
        event_type="FAILED_PAYMENT",
        failure_reason="BANK_DECLINE",
        amount_paise=6_000_000,  # ₹60,000 — above auto-limit
        customer_segment="enterprise",
        seed=42,
        expected_outcome="ESCALATED",
        demo_note="RED-TEAM: exceeds auto-recovery limit → human required",
    ),
    DemoScenario(
        name="unknown_failure_escalation",
        event_type="FAILED_PAYMENT",
        failure_reason="UNKNOWN",
        amount_paise=399900,
        customer_segment="standard",
        seed=42,
        expected_outcome="ESCALATED",
        demo_note="UNKNOWN failure → low confidence → human review",
    ),
    DemoScenario(
        name="mandate_failure_subscription",
        event_type="FAILED_SUBSCRIPTION",
        failure_reason="MANDATE_FAILURE",
        amount_paise=99900,
        customer_segment="standard",
        seed=20,
        expected_outcome="RECOVERED",
        demo_note="Subscription mandate retry — recovered",
    ),
]
