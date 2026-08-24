"""
Simulation batch endpoints.
POST /simulation/run       — start a new simulation run
GET  /simulation/{id}      — get run status + results
GET  /simulation           — list all runs
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.recovery import SimulationRunRequest, SimulationRunResponse
from app.services.simulation_service import SimulationService

router = APIRouter()


@router.post("/run", response_model=SimulationRunResponse, status_code=202)
async def run_simulation(
    request: SimulationRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SimulationRunResponse:
    """
    Start a batch simulation. Runs asynchronously in background.
    All results are computed from real simulation data — never fabricated.
    """
    service = SimulationService(db)
    run = await service.create_run(request)
    background_tasks.add_task(service.execute_run, str(run.id))
    return SimulationRunResponse(
        simulation_id=run.simulation_id,
        status=run.status,
        label=run.label,
        is_baseline=run.is_baseline,
        num_events=run.num_events,
        random_seed=run.random_seed,
        created_at=run.created_at,
    )


@router.get("/{simulation_id}")
async def get_simulation(
    simulation_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SimulationService(db)
    run = await service.get_run(simulation_id)
    if not run:
        raise HTTPException(status_code=404, detail="Simulation run not found")
    return {
        "simulation_id": run.simulation_id,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "label": run.label,
        "is_baseline": run.is_baseline,
        "random_seed": run.random_seed,
        "policy_version": run.policy_version,
        "agent_version": run.agent_version,
        "num_events": run.num_events,
        "results": run.results,
        "revenue_at_risk_paise": run.revenue_at_risk_paise,
        "revenue_recovered_paise": run.revenue_recovered_paise,
        "recovery_rate_pct": run.recovery_rate_pct,
        "total_cases": run.total_cases,
        "recovered_cases": run.recovered_cases,
        "escalated_cases": run.escalated_cases,
        "policy_violations": run.policy_violations,
        "created_at": run.created_at,
    }


@router.get("")
async def list_simulations(db: AsyncSession = Depends(get_db)) -> list[dict]:
    service = SimulationService(db)
    return await service.list_runs()
