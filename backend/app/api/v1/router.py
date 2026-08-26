"""
API v1 router — mounts all endpoint modules.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    audit,
    auth,
    demo,
    environment,
    events,
    metrics,
    policies,
    recovery_cases,
    simulation,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(events.router, prefix="/events", tags=["Events"])
api_router.include_router(recovery_cases.router, prefix="/recovery-cases", tags=["Recovery Cases"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
api_router.include_router(policies.router, prefix="/policies", tags=["Policies"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(environment.router, prefix="/environment", tags=["Environment"])
api_router.include_router(demo.router, prefix="/demo", tags=["Demo"])
