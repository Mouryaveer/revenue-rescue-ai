"""
Environment endpoint — tells the UI which mode is active.
Used to show TEST MODE / SIMULATION MODE badge in the dashboard.
"""

from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("")
async def get_environment() -> dict:
    """
    Returns the current execution environment.
    The UI uses this to show the correct mode badge.
    NEVER returns actual credentials — only the mode name and labels.
    """
    is_razorpay_test = (
        settings.PAYMENT_PROVIDER == "razorpay_test"
        and settings.RAZORPAY_KEY_ID.startswith("rzp_test_")
    )

    mode = "RAZORPAY_TEST" if is_razorpay_test else "SIMULATION"
    llm_mode = "AI" if settings.LLM_PROVIDER == "openai" else "FALLBACK"

    return {
        "payment_mode": mode,
        "payment_label": "RAZORPAY TEST MODE" if is_razorpay_test else "SIMULATION MODE",
        "payment_description": (
            "Live Razorpay test environment — no real money"
            if is_razorpay_test else
            "Deterministic synthetic simulator"
        ),
        "llm_mode": llm_mode,
        "llm_label": f"AI MODE — {settings.OPENAI_MODEL}" if llm_mode == "AI" else "FALLBACK MODE — Deterministic",
        "demo_mode": settings.DEMO_MODE,
        "is_synthetic_data": True,  # always true — we never process real payments
    }
