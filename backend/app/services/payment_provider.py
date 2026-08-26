"""
Payment provider selection.

This product executes recoveries through the in-process simulator.
A Razorpay *test-mode* adapter is intentionally not wired: there is no
Razorpay SDK dependency and production keys are refused at config load.

Never present simulator outcomes as Razorpay live recoveries.
"""

from __future__ import annotations

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

PLACEHOLDER_MARKERS = ("your_test", "...", "changeme", "placeholder")


def is_production_razorpay_key(key_id: str) -> bool:
    return (key_id or "").startswith("rzp_live_")


def has_real_razorpay_test_credentials() -> bool:
    key_id = (settings.RAZORPAY_KEY_ID or "").strip()
    secret = (settings.RAZORPAY_KEY_SECRET or "").strip()
    if is_production_razorpay_key(key_id):
        return False
    if not key_id.startswith("rzp_test_"):
        return False
    lowered = key_id.lower()
    if any(m in lowered for m in PLACEHOLDER_MARKERS):
        return False
    if len(key_id) < 20 or not secret or any(m in secret.lower() for m in PLACEHOLDER_MARKERS):
        return False
    return True


def resolve_payment_mode() -> dict:
    """
    UI-safe mode descriptor. Never returns credentials.
    Razorpay test mode is only advertised when test keys are present AND
    PAYMENT_PROVIDER=razorpay_test. There is still no live Razorpay client
    in this codebase — callers must treat that as unimplemented.
    """
    if is_production_razorpay_key(settings.RAZORPAY_KEY_ID or ""):
        logger.error("razorpay_live_key_refused")
        return {
            "payment_mode": "SIMULATION",
            "payment_label": "SIMULATION MODE",
            "payment_description": "Production Razorpay keys refused — simulator only",
            "razorpay_adapter": "DISABLED",
        }

    requested = (settings.PAYMENT_PROVIDER or "simulator").lower()
    if requested == "razorpay_test":
        if not has_real_razorpay_test_credentials():
            logger.warning("razorpay_test_requested_without_credentials")
            return {
                "payment_mode": "SIMULATION",
                "payment_label": "SIMULATION MODE",
                "payment_description": "Razorpay test mode requested but test credentials are missing or placeholder — using simulator",
                "razorpay_adapter": "NOT_CONFIGURED",
            }
        # Credentials exist, but no HTTP adapter is implemented.
        logger.warning("razorpay_test_adapter_not_implemented")
        return {
            "payment_mode": "SIMULATION",
            "payment_label": "SIMULATION MODE",
            "payment_description": "Razorpay test adapter is not implemented — recoveries run in the synthetic simulator",
            "razorpay_adapter": "NOT_IMPLEMENTED",
        }

    return {
        "payment_mode": "SIMULATION",
        "payment_label": "SIMULATION MODE",
        "payment_description": "Deterministic synthetic simulator — no real money",
        "razorpay_adapter": "UNUSED",
    }
