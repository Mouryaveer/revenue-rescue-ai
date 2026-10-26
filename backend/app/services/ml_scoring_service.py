"""
ML Scoring Service — LightGBM Quantitative Recovery Predictor.

Responsibilities:
- Predict recovery probability using trained LightGBM model.
- Calculate expected economic value using explicit units and configurable assumptions.
- Provide recovery score (0–100) for case prioritization.
- Supply quantitative evidence to LangGraph agent nodes.
- Safe deterministic fallback when model artifact is missing, unreadable, or encounters an exception.
- Strictly distinguish ML prediction from rule-based retry timing recommendations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from app.core.config import settings
from app.services.scoring_service import RecoveryScoringService

logger = structlog.get_logger(__name__)

FEATURE_COLUMNS = [
    "event_type",
    "failure_reason",
    "payment_method",
    "device_type",
    "country",
    "amount_paise",
    "retry_count",
    "event_hour_utc",
    "event_dayofweek_utc",
    "event_month_utc",
]


class MLScoringService:
    def __init__(self, model_path: str | None = None) -> None:
        self._fallback_scorer = RecoveryScoringService()
        self.model_path = model_path or getattr(
            settings, "LIGHTGBM_MODEL_PATH", "models/artifacts/lightgbm_recovery_model.joblib"
        )
        self.is_trained: bool = False
        self.model_version: str = "none"
        self._preprocessor = None
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load trained LightGBM bundle. Never raise on missing or corrupt artifact."""
        path = Path(self.model_path or "models/artifacts/lightgbm_recovery_model.joblib")
        if not path.is_absolute():
            # Resolve relative to repo root or backend parent
            repo_root = Path(__file__).resolve().parents[3]
            candidate = repo_root / path
            if candidate.exists():
                path = candidate
            else:
                backend_root = Path(__file__).resolve().parents[2]
                candidate_backend = backend_root / path
                if candidate_backend.exists():
                    path = candidate_backend

        if not path.exists():
            logger.info(
                "ml_model_artifact_not_found",
                path=str(path),
                fallback_mode="deterministic_heuristic",
            )
            self.is_trained = False
            self.model_version = "not_trained_fallback"
            return

        try:
            import joblib

            bundle = joblib.load(path)
            self._preprocessor = bundle["preprocessor"]
            self._model = bundle["model"]
            self.model_version = bundle.get("model_version", "rr-lightgbm.v1")
            self.is_trained = True
            logger.info("ml_model_loaded_successfully", path=str(path), version=self.model_version)
        except Exception as e:
            logger.warning(
                "ml_model_load_failed",
                path=str(path),
                error=str(e),
                fallback_mode="deterministic_heuristic",
            )
            self.is_trained = False
            self.model_version = "load_error_fallback"

    @staticmethod
    def _safe_int(val: Any, default: int = 0) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _prepare_feature_row(self, raw: dict[str, Any]) -> pd.DataFrame:
        """Construct sanitized single-row dataframe matching training feature schema and order."""
        row: dict[str, Any] = {
            "event_type": str(raw.get("event_type", "FAILED_PAYMENT")),
            "failure_reason": str(raw.get("failure_reason", "UNKNOWN")),
            "payment_method": str(raw.get("payment_method", "card")),
            "device_type": str(raw.get("device_type", "web")),
            "country": str(raw.get("country", "IN")),
            "amount_paise": max(0, self._safe_int(raw.get("amount_paise", 0), 0)),
            "retry_count": max(0, self._safe_int(raw.get("retry_count", 0), 0)),
            "event_hour_utc": self._safe_int(raw.get("event_hour_utc", 12), 12) % 24,
            "event_dayofweek_utc": self._safe_int(raw.get("event_dayofweek_utc", 0), 0) % 7,
            "event_month_utc": max(1, min(12, self._safe_int(raw.get("event_month_utc", 1), 1))),
        }
        return pd.DataFrame([row])[FEATURE_COLUMNS]

    def predict_probability(self, features: dict[str, Any]) -> float:
        """
        Predict recovery probability in range [0.0, 1.0].
        If model is unavailable or inference fails, falls back to deterministic heuristic.
        Never fabricates an illustrative probability as a measured ML result.
        """
        if not self.is_trained or self._model is None or self._preprocessor is None:
            # Deterministic heuristic fallback
            failure_reason = str(features.get("failure_reason", "UNKNOWN"))
            amount_paise = int(features.get("amount_paise", 0))
            retry_count = int(features.get("retry_count", 0))
            raw_score = self._fallback_scorer.score(failure_reason, amount_paise, retry_count)
            return round(raw_score / 100.0, 4)

        try:
            df = self._prepare_feature_row(features)
            transformed = self._preprocessor.transform(df)
            prob = float(self._model.predict_proba(transformed)[0, 1])
            return round(max(0.0, min(1.0, prob)), 4)
        except Exception as e:
            logger.warning("ml_inference_failed_falling_back", error=str(e))
            failure_reason = str(features.get("failure_reason", "UNKNOWN"))
            amount_paise = int(features.get("amount_paise", 0))
            retry_count = int(features.get("retry_count", 0))
            raw_score = self._fallback_scorer.score(failure_reason, amount_paise, retry_count)
            return round(raw_score / 100.0, 4)

    def calculate_expected_value(
        self,
        probability: float,
        amount_paise: int,
        intervention_cost_paise: int = 500,
    ) -> float:
        """
        Calculate expected economic value in paise:
        EV(action) = P(recovery) * amount_paise - intervention_cost_paise

        Units & Assumptions:
        - probability: unitless, in [0.0, 1.0].
        - amount_paise: integer paise (100 paise = 1 INR).
        - intervention_cost_paise: estimated cost of SMS/WhatsApp/retry gateway fees.
          Default 500 paise (₹5.00 INR) is a configurable assumption, not an empirical cost.
        - Result is in paise (can be positive or negative).
        """
        prob = max(0.0, min(1.0, float(probability)))
        amount = max(0, int(amount_paise))
        cost = max(0, int(intervention_cost_paise))
        return round((prob * amount) - cost, 2)

    def get_recovery_score(self, features: dict[str, Any]) -> float:
        """
        Normalized recovery score in [0.0, 100.0] for case ranking.
        When ML model is active, this maps measured probability to a 0–100 scale.
        """
        prob = self.predict_probability(features)
        return round(prob * 100.0, 2)

    @staticmethod
    def get_rule_based_retry_delay_hours(failure_reason: str, retry_count: int = 0) -> int:
        """
        Rule-based retry delay recommendation.
        LABEL: Explicitly heuristic/rule-based, NOT ML-predicted.
        Subject to policy engine approval before execution.
        """
        delays = {
            "GATEWAY_TEMPORARY": 2,
            "INSUFFICIENT_FUNDS": 24 if retry_count == 0 else 48,
            "BANK_DECLINE": 48,
            "MANDATE_FAILURE": 24,
            "SUBSCRIPTION_GRACE": 24,
            "AUTH_FAILURE": 0,
            "EXPIRED_METHOD": 0,
            "CHECKOUT_ABANDONED": 1,
            "UNKNOWN": 24,
        }
        return delays.get(failure_reason, 24)

    def get_quantitative_evidence(self, features: dict[str, Any]) -> dict[str, Any]:
        """Produce complete quantitative evidence packet for LangGraph and audit ledger."""
        prob = self.predict_probability(features)
        amount_paise = int(features.get("amount_paise", 0))
        intervention_cost_paise = int(features.get("intervention_cost_paise", 500))
        ev_paise = self.calculate_expected_value(prob, amount_paise, intervention_cost_paise)
        score = self.get_recovery_score(features)
        failure_reason = str(features.get("failure_reason", "UNKNOWN"))
        retry_count = int(features.get("retry_count", 0))
        recommended_delay = self.get_rule_based_retry_delay_hours(failure_reason, retry_count)

        return {
            "model_version": self.model_version,
            "is_trained_model": self.is_trained,
            "scoring_mode": "lightgbm_tabular"
            if self.is_trained
            else "deterministic_heuristic_fallback",
            "recovery_probability": prob,
            "recovery_score": score,
            "amount_at_risk_paise": amount_paise,
            "intervention_cost_paise": intervention_cost_paise,
            "cost_assumption_basis": "Configurable operational fee estimate (500 paise = ₹5.00 INR)",
            "expected_value_paise": ev_paise,
            "expected_value_inr": round(ev_paise / 100.0, 2),
            "rule_based_retry_delay_hours": recommended_delay,
            "timing_recommendation_nature": "Deterministic rule-based heuristic (subject to policy authorization)",
        }
