"""
SimulationRun — tracks batch simulation experiment metadata for reproducibility.
"""

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedModel


class SimulationRun(TimestampedModel):
    __tablename__ = "simulation_runs"

    simulation_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="Simulation Run")

    # Reproducibility
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Config
    num_customers: Mapped[int] = mapped_column(Integer, nullable=False)
    num_events: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_rate: Mapped[float] = mapped_column(Float, nullable=False)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Results (computed after run — from real data, never fabricated)
    results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revenue_at_risk_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revenue_recovered_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovery_rate_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovered_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalated_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    policy_violations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
