"""
Idempotency key store — prevents duplicate event processing.
For MVP: uses DB (recovery_cases.source_event_key unique constraint).
For production: Redis-backed with TTL.

The check is: does a RecoveryCase already exist with this source_event_key?
If yes → return existing, don't reprocess.
"""

from __future__ import annotations

import hashlib


def make_idempotency_key(customer_id: str, amount_paise: int, failure_reason: str, extra: str = "") -> str:
    """
    Generate a deterministic idempotency key from event fields.
    Use this when the caller doesn't provide their own key.
    """
    raw = f"{customer_id}:{amount_paise}:{failure_reason}:{extra}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
