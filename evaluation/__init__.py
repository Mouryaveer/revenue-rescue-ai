"""Shared evaluation utilities for RevenueRescue AI (metrics, thresholds, bootstrap, reports)."""

from evaluation.metrics import (
    METRIC_INFO,
    MetricInputError,
    apply_threshold,
    evaluate_binary,
    evaluate_subgroups,
)

__all__ = [
    "METRIC_INFO",
    "MetricInputError",
    "apply_threshold",
    "evaluate_binary",
    "evaluate_subgroups",
]
