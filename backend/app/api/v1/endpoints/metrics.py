"""
Metrics endpoints — all numbers computed from real stored data.
Never fabricated. Never hard-coded.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.recovery import MetricsOverview
from app.services.metrics_service import MetricsService

router = APIRouter()


@router.get("/overview", response_model=MetricsOverview)
async def get_overview(
    simulation_run_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> MetricsOverview:
    """
    Real-time metrics computed from the database.
    simulation_run_id filters to a specific batch run.
    All numbers are computed — never fabricated.
    """
    service = MetricsService(db)
    return await service.compute_overview(simulation_run_id=simulation_run_id)


@router.get("/revenue-recovered")
async def get_revenue_recovered(
    simulation_run_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = MetricsService(db)
    return await service.get_revenue_recovered(simulation_run_id=simulation_run_id)


@router.get("/baseline-comparison")
async def get_baseline_comparison(
    ai_run_id: str,
    baseline_run_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Compare AI vs baseline run — both from real stored simulation data.
    Labels: BASELINE | REVENUERESCUE_AI
    """
    service = MetricsService(db)
    return await service.compare_runs(ai_run_id=ai_run_id, baseline_run_id=baseline_run_id)
