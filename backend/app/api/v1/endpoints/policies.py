"""
Policy management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.policy_service import PolicyService

router = APIRouter()


@router.get("")
async def list_policies(db: AsyncSession = Depends(get_db)) -> list[dict]:
    service = PolicyService(db)
    return await service.list_policies()


@router.get("/active")
async def get_active_policy(db: AsyncSession = Depends(get_db)) -> dict:
    service = PolicyService(db)
    policy = await service.get_active_policy()
    if not policy:
        raise HTTPException(status_code=404, detail="No active policy found")
    return policy


@router.post("", status_code=201)
async def create_policy(payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Create a new policy version.
    Policy changes are versioned — old decisions remain explainable.
    """
    service = PolicyService(db)
    return await service.create_policy(payload)
