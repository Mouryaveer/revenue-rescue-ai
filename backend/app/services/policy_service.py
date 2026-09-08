"""
Policy service — load, store, and version merchant policies.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy
from policies.schemas.policy_schema import PolicyConfig


def _find_policy_path() -> Path:
    """Find the merchant_default_v1.json wherever the project root is."""
    # Try: relative to this file → backend/app/services → ../../../../policies/defaults/
    candidates = [
        Path(__file__).parent.parent.parent.parent / "policies" / "defaults" / "merchant_default_v1.json",
        Path("/app/policies/defaults/merchant_default_v1.json"),
        Path("policies/defaults/merchant_default_v1.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    # Last resort — return first candidate and let it fail with a clear message
    return candidates[0]


_DEFAULT_POLICY_PATH = _find_policy_path()


class PolicyService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_active_policy(self) -> dict | None:
        result = await self._db.execute(
            select(Policy).where(Policy.is_active == True).order_by(Policy.version.desc()).limit(1)
        )
        policy = result.scalar_one_or_none()
        if policy:
            return {"policy_id": policy.policy_id, "version": policy.version, "config": policy.config}
        return None

    async def get_active_policy_config(self) -> PolicyConfig:
        """Return a validated PolicyConfig. Falls back to default if DB has none."""
        active = await self.get_active_policy()
        if active:
            return PolicyConfig(**{"policy_id": active["policy_id"], "version": active["version"], **active["config"]})

        # Load default from file
        raw = json.loads(_DEFAULT_POLICY_PATH.read_text())
        return PolicyConfig(**raw)

    async def list_policies(self) -> list[dict]:
        result = await self._db.execute(select(Policy).order_by(Policy.version.desc()))
        return [
            {"policy_id": p.policy_id, "version": p.version, "is_active": p.is_active, "config": p.config}
            for p in result.scalars().all()
        ]

    async def create_policy(self, payload: dict) -> dict:
        # Deactivate existing active policy
        existing = await self._db.execute(select(Policy).where(Policy.is_active == True))
        for p in existing.scalars().all():
            p.is_active = False

        policy_id = payload.get("policy_id", "merchant_default")
        version = payload.get("version", 1)

        new_policy = Policy(
            policy_id=policy_id,
            version=version,
            is_active=True,
            config=payload,
            description=payload.get("description"),
        )
        self._db.add(new_policy)
        await self._db.flush()
        return {"policy_id": policy_id, "version": version, "status": "CREATED"}
