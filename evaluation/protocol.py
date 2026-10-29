"""
Evaluation protocol helpers: threshold analysis, validation-only threshold selection,
bootstrap confidence intervals and validation-selected probability calibration.

Rules enforced here
-------------------
* Thresholds and calibrators are chosen from **validation** data only. Functions that select take
  validation arrays; the caller applies the frozen choice to the test split.
* All candidate thresholds are reported from one operating point each: a row of the threshold table
  is a single confusion matrix, never a mix of per-metric optima.
* Bootstrap uses the percentile method with a fixed seed. Resamples where a metric is undefined
  (for example a single-class resample for ROC-AUC) are skipped and counted.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold

from evaluation.metrics import (
    LOG_LOSS_EPS,
    MetricInputError,
    classification_metrics_from_counts,
    evaluate_binary,
    validate_inputs,
)

DEFAULT_GRID = np.round(np.arange(0.05, 0.951, 0.01), 2)
BOOTSTRAP_METRICS = ("roc_auc", "pr_auc", "precision", "recall", "f1", "brier", "log_loss", "mcc")


# ─────────────────────────────────────────────────────────────────────────────
# Threshold analysis
# ─────────────────────────────────────────────────────────────────────────────
def _counts_at(y: np.ndarray, p: np.ndarray, t: float) -> dict[str, int]:
    pred = p >= t
    return {
        "tn": int(((y == 0) & ~pred).sum()),
        "fp": int(((y == 0) & pred).sum()),
        "fn": int(((y == 1) & ~pred).sum()),
        "tp": int(((y == 1) & pred).sum()),
    }


def threshold_table(
    y_true: Any, y_prob: Any, thresholds: Sequence[float] | np.ndarray = DEFAULT_GRID
) -> list[dict[str, Any]]:
    """One row per threshold, each computed from a single confusion matrix."""
    y, p, _, _ = validate_inputs(y_true, y_prob)
    assert p is not None
    rows = []
    for t in thresholds:
        cm = _counts_at(y, p, float(t))
        m = classification_metrics_from_counts(**cm)
        rows.append({"threshold": float(t), **cm, **m.values})
    return rows


@dataclass(frozen=True)
class ThresholdChoice:
    method: str
    threshold: float
    criterion: str
    feasible: bool
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "threshold": self.threshold,
            "criterion": self.criterion,
            "feasible": self.feasible,
            "note": self.note,
        }


def select_threshold(
    y_val: Any,
    p_val: Any,
    method: str = "youden",
    *,
    thresholds: Sequence[float] | np.ndarray = DEFAULT_GRID,
    fixed: float = 0.5,
    target_precision: float = 0.80,
    min_coverage: float = 0.05,
) -> ThresholdChoice:
    """Select an operating threshold on validation data.

    Methods
    -------
    ``fixed``          use ``fixed`` unchanged.
    ``youden``         maximise TPR − FPR (equivalently balanced accuracy).
    ``max_f1``         maximise F1.
    ``max_mcc``        maximise MCC.
    ``min_precision``  lowest threshold whose validation precision ≥ ``target_precision`` with
                       coverage ≥ ``min_coverage`` (high-confidence tier). If none qualifies,
                       returns the highest-precision threshold and ``feasible=False``.
    Ties are broken by the lowest threshold.
    """
    if method == "fixed":
        return ThresholdChoice("fixed", float(fixed), f"fixed at {fixed}", True)
    rows = threshold_table(y_val, p_val, thresholds)

    def best(key: str) -> dict[str, Any]:
        valid = [r for r in rows if r[key] is not None]
        if not valid:
            raise MetricInputError(f"{key} is undefined at every candidate threshold")
        return max(valid, key=lambda r: (r[key], -r["threshold"]))

    if method == "youden":
        r = best("balanced_accuracy")
        return ThresholdChoice(method, r["threshold"], "max TPR - FPR on validation", True)
    if method == "max_f1":
        return ThresholdChoice(method, best("f1")["threshold"], "max F1 on validation", True)
    if method == "max_mcc":
        return ThresholdChoice(method, best("mcc")["threshold"], "max MCC on validation", True)
    if method == "min_precision":
        ok = [
            r
            for r in rows
            if r["precision"] is not None
            and r["precision"] >= target_precision
            and r["coverage"] >= min_coverage
        ]
        crit = f"lowest threshold with validation precision >= {target_precision:.2f} and coverage >= {min_coverage:.2f}"
        if ok:
            return ThresholdChoice(method, min(r["threshold"] for r in ok), crit, True)
        cand = [r for r in rows if r["precision"] is not None and r["coverage"] >= min_coverage]
        r = max(cand, key=lambda r: (r["precision"], -r["threshold"])) if cand else rows[-1]
        return ThresholdChoice(
            method,
            r["threshold"],
            crit,
            False,
            f"target not reachable on validation; best precision {r['precision']} at {r['threshold']}",
        )
    raise ValueError(f"unknown threshold method {method!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────
def bootstrap_ci(
    y_true: Any,
    y_prob: Any,
    threshold: float,
    metrics: Sequence[str] = BOOTSTRAP_METRICS,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
    min_valid: int = 100,
) -> dict[str, dict[str, Any]]:
    """Percentile bootstrap CIs (resampling rows with replacement).

    Returns ``{metric: {point, low, high, n_valid, n_skipped, status}}``. If fewer than
    ``min_valid`` resamples define the metric, the interval is ``None`` with a status message.
    """
    y, p, _, _ = validate_inputs(y_true, y_prob)
    assert p is not None
    point = evaluate_binary(y, p, threshold=threshold)["metrics"]
    rng = np.random.default_rng(seed)
    n = y.size
    samples: dict[str, list[float]] = {m: [] for m in metrics}
    skipped = dict.fromkeys(metrics, 0)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        vals = _fast_metrics(y[idx], p[idx], threshold)
        for m in metrics:
            v = vals.get(m)
            if v is None:
                skipped[m] += 1
            else:
                samples[m].append(v)
    out = {}
    for m in metrics:
        s = np.asarray(samples[m])
        row: dict[str, Any] = {
            "point": point.get(m),
            "n_valid": int(s.size),
            "n_skipped": skipped[m],
            "method": f"percentile bootstrap, {n_boot} resamples, seed {seed}",
        }
        if s.size < min_valid:
            row.update(low=None, high=None, status=f"insufficient valid resamples ({s.size})")
        else:
            row.update(
                low=float(np.quantile(s, alpha / 2)),
                high=float(np.quantile(s, 1 - alpha / 2)),
                status="ok",
            )
        out[m] = row
    return out


def _fast_metrics(y: np.ndarray, p: np.ndarray, t: float) -> dict[str, float | None]:
    """Metric subset for bootstrap loops; definitions match evaluation.metrics."""
    from sklearn.metrics import average_precision_score, roc_auc_score

    out: dict[str, float | None] = {}
    two = y.min() != y.max()
    out["roc_auc"] = float(roc_auc_score(y, p)) if two else None
    out["pr_auc"] = float(average_precision_score(y, p)) if two else None
    out["brier"] = float(np.mean((p - y) ** 2))
    pc = np.clip(p, LOG_LOSS_EPS, 1 - LOG_LOSS_EPS)
    out["log_loss"] = float(-np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)))
    out.update(classification_metrics_from_counts(**_counts_at(y, p, t)).values)
    return out


def paired_bootstrap_difference(
    y_true: Any,
    p_a: Any,
    p_b: Any,
    metric: str = "roc_auc",
    threshold: float = 0.5,
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """CI for metric(A) − metric(B) using the same resampled rows for both models."""
    y, pa, _, _ = validate_inputs(y_true, p_a)
    _, pb, _, _ = validate_inputs(y_true, p_b)
    assert pa is not None and pb is not None
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, y.size, y.size)
        a = _fast_metrics(y[idx], pa[idx], threshold)[metric]
        b = _fast_metrics(y[idx], pb[idx], threshold)[metric]
        if a is not None and b is not None:
            diffs.append(a - b)
    d = np.asarray(diffs)
    pa_m = _fast_metrics(y, pa, threshold)[metric]
    pb_m = _fast_metrics(y, pb, threshold)[metric]
    point = None if pa_m is None or pb_m is None else pa_m - pb_m
    return {
        "metric": metric,
        "difference": point,
        "low": float(np.quantile(d, alpha / 2)) if d.size else None,
        "high": float(np.quantile(d, 1 - alpha / 2)) if d.size else None,
        "n_valid": int(d.size),
        "share_resamples_a_better": float((d > 0).mean()) if d.size else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Calibration (selected on validation by cross-fitting)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Calibrator:
    """Monotone map from raw model probability to calibrated probability."""

    method: str
    model: Any = None

    def fit(self, p: np.ndarray, y: np.ndarray) -> Calibrator:
        if self.method == "none":
            return self
        if self.method == "sigmoid":
            self.model = LogisticRegression(C=1e6, solver="lbfgs").fit(_logit(p)[:, None], y)
        elif self.method == "isotonic":
            self.model = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(p, y)
        else:
            raise ValueError(f"unknown calibration method {self.method!r}")
        return self

    def transform(self, p: Any) -> np.ndarray:
        p = np.asarray(p, dtype=float)
        if self.method == "none":
            return p
        if self.method == "sigmoid":
            return self.model.predict_proba(_logit(p)[:, None])[:, 1]
        return np.clip(self.model.predict(p), 0.0, 1.0)

    def params(self) -> dict[str, Any]:
        if self.method == "sigmoid":
            return {"coef": float(self.model.coef_[0][0]), "intercept": float(self.model.intercept_[0])}
        if self.method == "isotonic":
            return {
                "x": self.model.X_thresholds_.tolist(),
                "y": self.model.y_thresholds_.tolist(),
            }
        return {}


def _logit(p: np.ndarray) -> np.ndarray:
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(pc / (1 - pc))


def select_calibration(
    y_val: Any,
    p_val: Any,
    methods: Sequence[str] = ("none", "sigmoid", "isotonic"),
    n_splits: int = 5,
    seed: int = 42,
    min_improvement: float = 1e-4,
) -> dict[str, Any]:
    """Choose a calibration method by K-fold cross-fitted log loss on validation.

    Each fold's calibrator is fitted on the other folds, so the comparison is out-of-sample within
    validation. A method replaces ``none`` only if it lowers log loss by ``min_improvement``.
    Returns the chosen fitted calibrator (refit on all validation rows), the cross-fitted
    validation probabilities for threshold selection, and the comparison table.
    """
    y, p, _, _ = validate_inputs(y_val, p_val)
    assert p is not None
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    table, oof = [], {}
    for m in methods:
        out = np.empty_like(p)
        for tr, te in skf.split(p, y):
            out[te] = Calibrator(m).fit(p[tr], y[tr]).transform(p[te])
        oof[m] = out
        r = evaluate_binary(y, out, threshold=0.5)["metrics"]
        table.append({"method": m, "cv_log_loss": r["log_loss"], "cv_brier": r["brier"], "cv_ece": r["ece"]})
    base = next(t for t in table if t["method"] == "none")["cv_log_loss"]
    best = min(table, key=lambda t: t["cv_log_loss"])
    chosen = best["method"] if base - best["cv_log_loss"] >= min_improvement else "none"
    cal = Calibrator(chosen).fit(p, y)
    return {
        "method": chosen,
        "calibrator": cal,
        "cross_fitted_validation_probs": oof[chosen] if chosen != "none" else p,
        "comparison": table,
        "selection_rule": f"{n_splits}-fold cross-fitted validation log loss; must improve by >= {min_improvement}",
    }


def run_selection(
    y_val: Any,
    p_val: Any,
    methods: dict[str, dict[str, Any]],
) -> dict[str, ThresholdChoice]:
    """Apply several threshold-selection methods to the same validation probabilities."""
    return {name: select_threshold(y_val, p_val, **kw) for name, kw in methods.items()}
