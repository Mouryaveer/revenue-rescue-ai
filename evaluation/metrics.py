"""
Centralised evaluation metrics for the binary ``recovered`` target.

Every notebook, training script and report in RevenueRescue AI computes metrics through this
module, so a metric has exactly one definition in the project.

Conventions
-----------
* ``y_true`` holds binary labels (0/1 or bool). ``y_prob`` holds predicted probabilities of the
  positive class (recovered = 1) in ``[0, 1]``.
* Threshold-dependent metrics use ``y_pred = (y_prob >= threshold)`` unless explicit ``y_pred``
  labels are passed.
* Invalid *input* (empty arrays, NaN/inf, probabilities outside ``[0, 1]``, non-binary labels,
  length mismatch, negative weights) raises :class:`MetricInputError`.
* A metric that is *mathematically undefined* for valid input (for example ROC-AUC on a single
  class, or precision with no predicted positives) is returned as ``None`` and its reason is put in
  ``undefined[metric_name]``. Undefined metrics are never replaced by 0.
* Values are stored at full float precision. Rounding happens only when rendering Markdown.
* Probabilities are clipped to ``[LOG_LOSS_EPS, 1 - LOG_LOSS_EPS]`` for log loss only.

Metric families
---------------
``ranking``          ROC-AUC, PR-AUC — use continuous probabilities.
``probability``      log loss, Brier, calibration — use probabilities.
``probability_error`` regression-style errors between probability and 0/1 label.
``classification``   confusion-matrix metrics at one operating threshold.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

LOG_LOSS_EPS = 1e-15
DEFAULT_THRESHOLD = 0.5
DEFAULT_CALIBRATION_BINS = 10
DEFAULT_MIN_BIN_COUNT = 30
DEFAULT_MIN_SUBGROUP_SIZE = 50


class MetricInputError(ValueError):
    """Raised when metric inputs are invalid (as opposed to a metric being undefined)."""


@dataclass(frozen=True)
class MetricInfo:
    name: str
    full_name: str
    family: str
    formula: str
    note: str = ""


METRIC_INFO: dict[str, MetricInfo] = {
    m.name: m
    for m in [
        # Probability-error (regression-style) metrics on probabilities vs 0/1 labels
        MetricInfo("mse", "Mean Squared Error", "probability_error", "mean((p - y)^2)",
                   "Equal to the Brier score for binary labels."),
        MetricInfo("rmse", "Root Mean Squared Error", "probability_error", "sqrt(MSE)"),
        MetricInfo("mae", "Mean Absolute Error", "probability_error", "mean(|p - y|)"),
        MetricInfo("medae", "Median Absolute Error", "probability_error", "median(|p - y|)"),
        MetricInfo("mean_error", "Bias / Mean Error", "probability_error", "mean(p - y)",
                   "Positive = over-predicts recovery on average."),
        MetricInfo("r2", "Coefficient of Determination", "probability_error",
                   "1 - sum((y - p)^2) / sum((y - mean(y))^2)",
                   "Brier skill score against the test-set prevalence; undefined for a constant target."),
        MetricInfo("nrmse_range", "Normalised RMSE (by target range)", "probability_error",
                   "RMSE / (max(y) - min(y))",
                   "Equals RMSE when both classes are present; undefined for a zero-range target."),
        MetricInfo("mape_nonzero_pct", "Mean Absolute Percentage Error (non-zero targets only)",
                   "probability_error", "100 * mean(|p - y| / |y|) over y != 0",
                   "Rows with y = 0 are excluded and counted; for binary labels this is "
                   "100 * mean(1 - p) over positives. Not a primary metric."),
        # Ranking
        MetricInfo("roc_auc", "Area Under the ROC Curve", "ranking",
                   "P(score of random positive > score of random negative)",
                   "Undefined when only one class is present."),
        MetricInfo("pr_auc", "Average Precision (PR-AUC)", "ranking",
                   "sum_k (R_k - R_{k-1}) * P_k", "Baseline equals positive prevalence."),
        # Probability quality
        MetricInfo("log_loss", "Log Loss / Cross-Entropy", "probability",
                   "-mean(y log p + (1 - y) log(1 - p))",
                   f"Probabilities clipped to [{LOG_LOSS_EPS}, 1 - {LOG_LOSS_EPS}]."),
        MetricInfo("brier", "Brier Score", "probability", "mean((p - y)^2)"),
        MetricInfo("ece", "Expected Calibration Error", "probability",
                   "sum_b (n_b / n) * |mean(y)_b - mean(p)_b|", "Equal-width bins."),
        MetricInfo("mce", "Maximum Calibration Error", "probability",
                   "max_b |mean(y)_b - mean(p)_b|", "Over non-empty bins."),
        # Classification at a threshold
        MetricInfo("accuracy", "Classification Accuracy", "classification", "(TP + TN) / N",
                   "Misleading under imbalance: predicting all positives scores the prevalence."),
        MetricInfo("precision", "Precision / Positive Predictive Value", "classification",
                   "TP / (TP + FP)", "Undefined with no predicted positives."),
        MetricInfo("recall", "Recall / Sensitivity / True Positive Rate", "classification",
                   "TP / (TP + FN)", "Undefined with no actual positives."),
        MetricInfo("f1", "F1-score", "classification", "2TP / (2TP + FP + FN)",
                   "Undefined when TP + FP + FN = 0."),
        MetricInfo("specificity", "Specificity / True Negative Rate", "classification",
                   "TN / (TN + FP)", "Undefined with no actual negatives."),
        MetricInfo("npv", "Negative Predictive Value", "classification", "TN / (TN + FN)",
                   "Undefined with no predicted negatives."),
        MetricInfo("fpr", "False Positive Rate", "classification", "FP / (FP + TN)"),
        MetricInfo("fnr", "False Negative Rate", "classification", "FN / (FN + TP)"),
        MetricInfo("balanced_accuracy", "Balanced Accuracy", "classification",
                   "(recall + specificity) / 2", "Undefined unless both classes are present."),
        MetricInfo("mcc", "Matthews Correlation Coefficient", "classification",
                   "(TP*TN - FP*FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN))",
                   "Undefined when any confusion-matrix margin is zero."),
        MetricInfo("cohen_kappa", "Cohen's Kappa", "classification", "(p_o - p_e) / (1 - p_e)",
                   "Undefined when p_e = 1."),
        MetricInfo("coverage", "Prediction coverage", "classification",
                   "(TP + FP) / N", "Share of rows selected as positive at the threshold."),
    ]
}

PROBABILITY_ERROR_METRICS = [k for k, v in METRIC_INFO.items() if v.family == "probability_error"]
CLASSIFICATION_METRICS = [k for k, v in METRIC_INFO.items() if v.family == "classification"]


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────
def _as_1d_float(values: Any, name: str) -> np.ndarray:
    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise MetricInputError(f"{name} must be numeric: {exc}") from exc
    if arr.ndim != 1:
        raise MetricInputError(f"{name} must be one-dimensional, got shape {arr.shape}")
    if arr.size == 0:
        raise MetricInputError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise MetricInputError(
            f"{name} contains {int((~np.isfinite(arr)).sum())} NaN or infinite values"
        )
    return arr


def _validate_binary(values: Any, name: str) -> np.ndarray:
    arr = _as_1d_float(values, name)
    bad = ~np.isin(arr, (0.0, 1.0))
    if bad.any():
        raise MetricInputError(
            f"{name} must contain only 0/1 labels; found {np.unique(arr[bad])[:5].tolist()}"
        )
    return arr.astype(np.int8)


def validate_inputs(
    y_true: Any,
    y_prob: Any | None = None,
    y_pred: Any | None = None,
    sample_weight: Any | None = None,
) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None, np.ndarray]:
    """Validate and convert inputs. Returns ``(y, p, y_pred, w)``; ``w`` defaults to ones."""
    y = _validate_binary(y_true, "y_true")
    n = y.size
    p = None
    if y_prob is not None:
        p = _as_1d_float(y_prob, "y_prob")
        if p.size != n:
            raise MetricInputError(f"y_prob has length {p.size}, y_true has length {n}")
        if (p < 0).any() or (p > 1).any():
            raise MetricInputError(
                f"y_prob must be in [0, 1]; range is [{p.min():.6g}, {p.max():.6g}]"
            )
    yp = None
    if y_pred is not None:
        yp = _validate_binary(y_pred, "y_pred")
        if yp.size != n:
            raise MetricInputError(f"y_pred has length {yp.size}, y_true has length {n}")
    if sample_weight is None:
        w = np.ones(n, dtype=float)
    else:
        w = _as_1d_float(sample_weight, "sample_weight")
        if w.size != n:
            raise MetricInputError(f"sample_weight has length {w.size}, y_true has length {n}")
        if (w < 0).any():
            raise MetricInputError("sample_weight must be non-negative")
        if w.sum() <= 0:
            raise MetricInputError("sample_weight must have a positive sum")
    return y, p, yp, w


def validate_threshold(threshold: float) -> float:
    t = float(threshold)
    if not math.isfinite(t) or t < 0 or t > 1:
        raise MetricInputError(f"threshold must be a finite number in [0, 1], got {threshold!r}")
    return t


def apply_threshold(y_prob: Any, threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
    """Binary labels using the project rule ``prob >= threshold``."""
    p = _as_1d_float(y_prob, "y_prob")
    return (p >= validate_threshold(threshold)).astype(np.int8)


# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class MetricResult:
    """Metric values plus the reasons for any undefined value."""

    values: dict[str, float | int | None] = field(default_factory=dict)
    undefined: dict[str, str] = field(default_factory=dict)

    def set(self, name: str, value: float | None, reason: str | None = None) -> None:
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            self.values[name] = None
            self.undefined[name] = reason or "undefined"
        else:
            self.values[name] = float(value)

    def merge(self, other: MetricResult) -> None:
        self.values.update(other.values)
        self.undefined.update(other.undefined)


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def _wmean(x: np.ndarray, w: np.ndarray) -> float:
    return float(np.sum(x * w) / np.sum(w))


def _weighted_median(x: np.ndarray, w: np.ndarray) -> float:
    if np.all(w == w[0]):
        return float(np.median(x))
    order = np.argsort(x, kind="mergesort")
    xs, cw = x[order], np.cumsum(w[order])
    return float(xs[np.searchsorted(cw, 0.5 * cw[-1])])


# ─────────────────────────────────────────────────────────────────────────────
# Metric families
# ─────────────────────────────────────────────────────────────────────────────
def probability_error_metrics(
    y_true: Any, y_prob: Any, sample_weight: Any | None = None
) -> MetricResult:
    """Regression-style errors between predicted probabilities and binary labels."""
    y, p, _, w = validate_inputs(y_true, y_prob, sample_weight=sample_weight)
    assert p is not None
    yf = y.astype(float)
    err = p - yf
    out = MetricResult()
    mse = _wmean(err**2, w)
    rmse = math.sqrt(mse)
    out.set("mse", mse)
    out.set("rmse", rmse)
    out.set("mae", _wmean(np.abs(err), w))
    out.set("medae", _weighted_median(np.abs(err), w))
    out.set("mean_error", _wmean(err, w))

    y_mean = _wmean(yf, w)
    ss_tot = float(np.sum(w * (yf - y_mean) ** 2))
    ss_res = float(np.sum(w * err**2))
    if ss_tot == 0:
        out.set("r2", None, "target is constant (zero variance); R² is undefined")
    else:
        out.set("r2", 1.0 - ss_res / ss_tot)

    target_range = float(yf.max() - yf.min())
    if target_range == 0:
        out.set(
            "nrmse_range",
            None,
            "target range is zero (single class); NRMSE by range is undefined. "
            "RMSE is reported unnormalised; no alternative denominator is substituted.",
        )
    else:
        out.set("nrmse_range", rmse / target_range)

    nonzero = yf != 0
    excluded = int((~nonzero).sum())
    out.values["mape_excluded_zero_targets"] = excluded
    out.values["mape_included_rows"] = int(nonzero.sum())
    if not nonzero.any():
        out.set("mape_nonzero_pct", None, "all targets are zero; percentage error is undefined")
    else:
        ape = np.abs(err[nonzero]) / np.abs(yf[nonzero])
        out.set("mape_nonzero_pct", 100.0 * _wmean(ape, w[nonzero]))
    return out


def ranking_metrics(y_true: Any, y_prob: Any, sample_weight: Any | None = None) -> MetricResult:
    y, p, _, w = validate_inputs(y_true, y_prob, sample_weight=sample_weight)
    out = MetricResult()
    if np.unique(y).size < 2:
        reason = "only one class present in y_true"
        out.set("roc_auc", None, reason)
        out.set("pr_auc", None, reason)
        return out
    out.set("roc_auc", float(roc_auc_score(y, p, sample_weight=w)))
    out.set("pr_auc", float(average_precision_score(y, p, sample_weight=w)))
    return out


def calibration_bins(
    y_true: Any,
    y_prob: Any,
    n_bins: int = DEFAULT_CALIBRATION_BINS,
    min_bin_count: int = DEFAULT_MIN_BIN_COUNT,
    sample_weight: Any | None = None,
) -> list[dict[str, Any]]:
    """Equal-width reliability bins. The last bin includes 1.0."""
    if n_bins < 1:
        raise MetricInputError("n_bins must be >= 1")
    y, p, _, w = validate_inputs(y_true, y_prob, sample_weight=sample_weight)
    assert p is not None
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    bins = []
    for b in range(n_bins):
        m = idx == b
        count = int(m.sum())
        row: dict[str, Any] = {
            "bin": b,
            "lower": float(edges[b]),
            "upper": float(edges[b + 1]),
            "count": count,
            "weight": float(w[m].sum()),
            "mean_predicted": None,
            "observed_rate": None,
            "abs_gap": None,
            "low_count": count < min_bin_count,
        }
        if count:
            mp, obs = _wmean(p[m], w[m]), _wmean(y[m].astype(float), w[m])
            row.update(mean_predicted=mp, observed_rate=obs, abs_gap=abs(obs - mp))
        bins.append(row)
    return bins


def probability_metrics(
    y_true: Any,
    y_prob: Any,
    sample_weight: Any | None = None,
    n_bins: int = DEFAULT_CALIBRATION_BINS,
) -> tuple[MetricResult, list[dict[str, Any]]]:
    y, p, _, w = validate_inputs(y_true, y_prob, sample_weight=sample_weight)
    assert p is not None
    out = MetricResult()
    pc = np.clip(p, LOG_LOSS_EPS, 1 - LOG_LOSS_EPS)
    out.set("log_loss", float(log_loss(y, pc, labels=[0, 1], sample_weight=w)))
    out.set("brier", _wmean((p - y) ** 2, w))
    bins = calibration_bins(y, p, n_bins=n_bins, sample_weight=w)
    total = float(w.sum())
    filled = [b for b in bins if b["count"]]
    out.set("ece", sum(b["weight"] / total * b["abs_gap"] for b in filled))
    out.set("mce", max(b["abs_gap"] for b in filled))
    return out, bins


def confusion_counts(
    y_true: Any, y_pred: Any, sample_weight: Any | None = None
) -> dict[str, float]:
    y, _, yp, w = validate_inputs(y_true, y_pred=y_pred, sample_weight=sample_weight)
    assert yp is not None
    return {
        "tn": float(w[(y == 0) & (yp == 0)].sum()),
        "fp": float(w[(y == 0) & (yp == 1)].sum()),
        "fn": float(w[(y == 1) & (yp == 0)].sum()),
        "tp": float(w[(y == 1) & (yp == 1)].sum()),
    }


def classification_metrics_from_counts(tn: float, fp: float, fn: float, tp: float) -> MetricResult:
    """All threshold-dependent metrics from one confusion matrix."""
    out = MetricResult()
    n = tn + fp + fn + tp
    if n <= 0:
        raise MetricInputError("confusion matrix is empty")
    pos, neg, pred_pos, pred_neg = tp + fn, tn + fp, tp + fp, tn + fn

    out.set("accuracy", (tp + tn) / n)
    out.set("precision", _ratio(tp, pred_pos), "no predicted positives (TP + FP = 0)")
    out.set("recall", _ratio(tp, pos), "no actual positives (TP + FN = 0)")
    out.set("specificity", _ratio(tn, neg), "no actual negatives (TN + FP = 0)")
    out.set("npv", _ratio(tn, pred_neg), "no predicted negatives (TN + FN = 0)")
    out.set("fpr", _ratio(fp, neg), "no actual negatives (TN + FP = 0)")
    out.set("fnr", _ratio(fn, pos), "no actual positives (TP + FN = 0)")
    out.set("f1", _ratio(2 * tp, 2 * tp + fp + fn), "TP + FP + FN = 0")
    rec, spec = out.values["recall"], out.values["specificity"]
    if rec is None or spec is None:
        out.set("balanced_accuracy", None, "requires both actual classes")
    else:
        out.set("balanced_accuracy", (rec + spec) / 2)
    den = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    if den == 0:
        out.set("mcc", None, "a confusion-matrix margin is zero (single class actual or predicted)")
    else:
        out.set("mcc", (tp * tn - fp * fn) / math.sqrt(den))
    po = (tp + tn) / n
    pe = (pred_pos * pos + pred_neg * neg) / (n * n)
    if math.isclose(pe, 1.0):
        out.set("cohen_kappa", None, "expected agreement p_e = 1")
    else:
        out.set("cohen_kappa", (po - pe) / (1 - pe))
    out.set("coverage", pred_pos / n)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────
def evaluate_binary(
    y_true: Any,
    y_prob: Any | None = None,
    threshold: float | None = DEFAULT_THRESHOLD,
    y_pred: Any | None = None,
    sample_weight: Any | None = None,
    n_bins: int = DEFAULT_CALIBRATION_BINS,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute every applicable metric and return a JSON-serialisable dict.

    Pass ``y_prob`` to get ranking, probability and probability-error metrics. Threshold-dependent
    metrics use explicit ``y_pred`` if given, else ``y_prob >= threshold``.
    """
    if y_prob is None and y_pred is None:
        raise MetricInputError("provide y_prob, y_pred, or both")
    y, p, yp, w = validate_inputs(y_true, y_prob, y_pred, sample_weight)
    if yp is None:
        assert p is not None
        if threshold is None:
            raise MetricInputError("threshold is required when y_pred is not given")
        thr: float | None = validate_threshold(threshold)
        yp = (p >= thr).astype(np.int8)
        label_source = "y_prob >= threshold"
    else:
        thr = None
        label_source = "explicit y_pred"

    result = MetricResult()
    bins: list[dict[str, Any]] = []
    if p is not None:
        result.merge(probability_error_metrics(y, p, w))
        result.merge(ranking_metrics(y, p, w))
        prob, bins = probability_metrics(y, p, w, n_bins=n_bins)
        result.merge(prob)
    cm = confusion_counts(y, yp, w)
    result.merge(classification_metrics_from_counts(**cm))

    weighted = sample_weight is not None
    return {
        "n": int(y.size),
        "weighted": weighted,
        "support": {"positive": int((y == 1).sum()), "negative": int((y == 0).sum())},
        "prevalence": _wmean(y.astype(float), w),
        "threshold": thr,
        "label_source": label_source,
        "confusion_matrix": cm if weighted else {k: int(v) for k, v in cm.items()},
        "metrics": result.values,
        "undefined": result.undefined,
        "calibration_bins": bins,
        "metadata": dict(metadata or {}),
    }


def evaluate_subgroups(
    y_true: Any,
    y_prob: Any,
    groups: Sequence[Any] | np.ndarray,
    threshold: float = DEFAULT_THRESHOLD,
    min_samples: int = DEFAULT_MIN_SUBGROUP_SIZE,
) -> list[dict[str, Any]]:
    """Per-subgroup metrics. Groups smaller than ``min_samples`` are reported, not scored."""
    y, p, _, _ = validate_inputs(y_true, y_prob)
    g = np.asarray(groups, dtype=object)
    if g.shape != y.shape:
        raise MetricInputError(f"groups has length {g.size}, y_true has length {y.size}")
    rows = []
    for value in sorted({str(v) for v in g}):
        m = np.array([str(v) == value for v in g])
        n = int(m.sum())
        row: dict[str, Any] = {"group": value, "n": n, "prevalence": float(y[m].mean())}
        if n < min_samples:
            row["status"] = f"insufficient_samples (n={n} < {min_samples})"
            row["metrics"] = None
        else:
            r = evaluate_binary(y[m], p[m], threshold=threshold)
            row["status"] = "ok"
            row["metrics"] = r["metrics"]
            row["undefined"] = r["undefined"]
            row["confusion_matrix"] = r["confusion_matrix"]
        rows.append(row)
    return rows


def to_jsonable(obj: Any) -> Any:
    """Convert numpy scalars/arrays and non-finite floats (→ None) for strict JSON."""
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [to_jsonable(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_ | bool):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating | float):
        f = float(obj)
        return f if math.isfinite(f) else None
    return obj


def dumps(obj: Any, **kwargs: Any) -> str:
    """Strict JSON (``allow_nan=False``) after :func:`to_jsonable`."""
    return json.dumps(to_jsonable(obj), allow_nan=False, **kwargs)
