"""Unit tests for evaluation.metrics. Formulas are cross-checked against scikit-learn."""

import json
import math

import numpy as np
import pytest
from sklearn import metrics as skm

from evaluation.metrics import (
    LOG_LOSS_EPS,
    METRIC_INFO,
    MetricInputError,
    apply_threshold,
    calibration_bins,
    classification_metrics_from_counts,
    dumps,
    evaluate_binary,
    evaluate_subgroups,
    probability_error_metrics,
)

REQUIRED = [
    "mse", "rmse", "mae", "mape_nonzero_pct", "r2", "nrmse_range", "medae", "mean_error",
    "accuracy", "precision", "recall", "f1", "specificity", "roc_auc", "log_loss", "mcc",
    "cohen_kappa", "balanced_accuracy", "pr_auc", "brier", "fpr", "fnr", "npv", "coverage",
]


@pytest.fixture
def random_case():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 500)
    p = np.clip(0.3 * y + rng.uniform(0, 0.7, 500), 0, 1)
    return y, p


def test_all_required_metrics_present_and_documented(random_case):
    y, p = random_case
    r = evaluate_binary(y, p, threshold=0.5)
    for name in REQUIRED:
        assert name in r["metrics"], name
        assert name in METRIC_INFO, name
    assert r["undefined"] == {}


def test_matches_sklearn(random_case):
    y, p = random_case
    pred = (p >= 0.5).astype(int)
    m = evaluate_binary(y, p, threshold=0.5)["metrics"]
    assert m["accuracy"] == pytest.approx(skm.accuracy_score(y, pred))
    assert m["precision"] == pytest.approx(skm.precision_score(y, pred))
    assert m["recall"] == pytest.approx(skm.recall_score(y, pred))
    assert m["f1"] == pytest.approx(skm.f1_score(y, pred))
    assert m["balanced_accuracy"] == pytest.approx(skm.balanced_accuracy_score(y, pred))
    assert m["mcc"] == pytest.approx(skm.matthews_corrcoef(y, pred))
    assert m["cohen_kappa"] == pytest.approx(skm.cohen_kappa_score(y, pred))
    assert m["roc_auc"] == pytest.approx(skm.roc_auc_score(y, p))
    assert m["pr_auc"] == pytest.approx(skm.average_precision_score(y, p))
    assert m["log_loss"] == pytest.approx(skm.log_loss(y, p))
    assert m["brier"] == pytest.approx(skm.brier_score_loss(y, p))
    assert m["mse"] == pytest.approx(skm.mean_squared_error(y, p))
    assert m["mae"] == pytest.approx(skm.mean_absolute_error(y, p))
    assert m["medae"] == pytest.approx(skm.median_absolute_error(y, p))
    assert m["r2"] == pytest.approx(skm.r2_score(y, p))
    assert m["rmse"] == pytest.approx(math.sqrt(m["mse"]))
    assert m["mean_error"] == pytest.approx(np.mean(p - y))
    tn, fp, fn, tp = skm.confusion_matrix(y, pred).ravel()
    assert m["specificity"] == pytest.approx(tn / (tn + fp))
    assert m["npv"] == pytest.approx(tn / (tn + fn))


def test_weighted_matches_sklearn(random_case):
    y, p = random_case
    w = np.random.default_rng(1).uniform(0.1, 3, y.size)
    pred = (p >= 0.5).astype(int)
    r = evaluate_binary(y, p, threshold=0.5, sample_weight=w)
    m = r["metrics"]
    assert r["weighted"] is True
    assert m["roc_auc"] == pytest.approx(skm.roc_auc_score(y, p, sample_weight=w))
    assert m["f1"] == pytest.approx(skm.f1_score(y, pred, sample_weight=w))
    assert m["mcc"] == pytest.approx(skm.matthews_corrcoef(y, pred, sample_weight=w))
    assert m["brier"] == pytest.approx(skm.brier_score_loss(y, p, sample_weight=w))


def test_perfect_predictions():
    y = np.array([0, 0, 1, 1])
    m = evaluate_binary(y, y.astype(float), threshold=0.5)["metrics"]
    for k in ["accuracy", "precision", "recall", "f1", "specificity", "roc_auc", "mcc",
              "cohen_kappa", "balanced_accuracy", "r2"]:
        assert m[k] == pytest.approx(1.0), k
    assert m["mse"] == 0 and m["mae"] == 0 and m["brier"] == 0
    assert m["log_loss"] == pytest.approx(-math.log(1 - LOG_LOSS_EPS), abs=1e-12)


def test_completely_wrong_predictions():
    y = np.array([0, 0, 1, 1])
    r = evaluate_binary(y, 1.0 - y, threshold=0.5)
    m = r["metrics"]
    assert m["accuracy"] == 0 and m["recall"] == 0 and m["precision"] == 0
    assert m["roc_auc"] == 0 and m["mcc"] == pytest.approx(-1.0)
    assert m["f1"] == 0  # 2TP/(2TP+FP+FN) = 0/4 is defined
    assert m["mse"] == 1 and m["r2"] == pytest.approx(-3.0)
    assert np.isfinite(m["log_loss"]) and m["log_loss"] > 30


def test_imbalanced_accuracy_vs_balanced_accuracy():
    y = np.array([1] * 95 + [0] * 5)
    m = evaluate_binary(y, np.ones(100), threshold=0.5)["metrics"]
    assert m["accuracy"] == pytest.approx(0.95)
    assert m["balanced_accuracy"] == pytest.approx(0.5)
    assert m["mcc"] is None  # predicted-negative margin is zero
    assert m["cohen_kappa"] == pytest.approx(0.0)


def test_no_predicted_positives():
    y = np.array([0, 1, 0, 1])
    r = evaluate_binary(y, np.full(4, 0.1), threshold=0.5)
    assert r["metrics"]["precision"] is None
    assert "no predicted positives" in r["undefined"]["precision"]
    assert r["metrics"]["recall"] == 0
    assert r["metrics"]["coverage"] == 0
    assert r["metrics"]["mcc"] is None
    assert r["metrics"]["roc_auc"] == pytest.approx(0.5)  # constant scores


def test_all_predicted_positives():
    y = np.array([0, 1, 0, 1])
    r = evaluate_binary(y, np.full(4, 0.9), threshold=0.5)
    m = r["metrics"]
    assert m["recall"] == 1 and m["specificity"] == 0 and m["coverage"] == 1
    assert m["npv"] is None and "no predicted negatives" in r["undefined"]["npv"]


def test_no_positive_labels():
    y = np.zeros(4, dtype=int)
    r = evaluate_binary(y, np.array([0.1, 0.6, 0.2, 0.3]), threshold=0.5)
    u = r["undefined"]
    for k in ["recall", "fnr", "roc_auc", "pr_auc", "balanced_accuracy", "r2", "nrmse_range",
              "mape_nonzero_pct"]:
        assert r["metrics"][k] is None and k in u, k
    assert r["metrics"]["specificity"] == pytest.approx(0.75)
    assert r["metrics"]["mape_excluded_zero_targets"] == 4


def test_no_negative_labels():
    y = np.ones(4, dtype=int)
    r = evaluate_binary(y, np.array([0.9, 0.4, 0.8, 0.7]), threshold=0.5)
    for k in ["specificity", "fpr", "roc_auc", "balanced_accuracy", "r2"]:
        assert r["metrics"][k] is None, k
    assert r["metrics"]["recall"] == pytest.approx(0.75)


def test_constant_probabilities():
    y = np.array([0, 1, 1, 0, 1])
    m = evaluate_binary(y, np.full(5, 0.6), threshold=0.5)["metrics"]
    assert m["roc_auc"] == pytest.approx(0.5)
    assert m["pr_auc"] == pytest.approx(0.6)
    assert m["r2"] == pytest.approx(0.0)  # constant = prevalence → R² 0


def test_zero_and_one_probabilities_log_loss_finite():
    y = np.array([0, 1])
    m = evaluate_binary(y, np.array([1.0, 0.0]), threshold=0.5)["metrics"]
    # 1 - (1 - eps) is not exactly eps in float64, hence the loose tolerance.
    assert m["log_loss"] == pytest.approx(-math.log(LOG_LOSS_EPS), rel=1e-2)
    # other metrics use unclipped probabilities
    assert m["mae"] == 1.0


@pytest.mark.parametrize(
    "y,p,msg",
    [
        ([0, 1], [0.2, 1.2], r"\[0, 1\]"),
        ([0, 1], [-0.1, 0.5], r"\[0, 1\]"),
        ([0, 1], [np.nan, 0.5], "NaN or infinite"),
        ([0, 1], [np.inf, 0.5], "NaN or infinite"),
        ([0, np.nan], [0.2, 0.5], "NaN or infinite"),
        ([], [], "empty"),
        ([0, 1, 1], [0.2, 0.5], "length"),
        ([0, 2], [0.2, 0.5], "0/1"),
        ([0, 1], ["a", 0.5], "numeric"),
    ],
)
def test_invalid_inputs_raise(y, p, msg):
    with pytest.raises(MetricInputError, match=msg):
        evaluate_binary(y, p)


def test_invalid_threshold_and_weights():
    with pytest.raises(MetricInputError, match="threshold"):
        evaluate_binary([0, 1], [0.1, 0.9], threshold=1.5)
    with pytest.raises(MetricInputError, match="threshold"):
        apply_threshold([0.1], float("nan"))
    with pytest.raises(MetricInputError, match="non-negative"):
        evaluate_binary([0, 1], [0.1, 0.9], sample_weight=[-1, 1])
    with pytest.raises(MetricInputError, match="provide"):
        evaluate_binary([0, 1])


def test_bool_labels_accepted():
    r = evaluate_binary(np.array([True, False]), np.array([0.8, 0.3]))
    assert r["metrics"]["accuracy"] == 1


def test_mape_zero_target_handling():
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.5, 0.75])
    m = probability_error_metrics(y, p).values
    assert m["mape_excluded_zero_targets"] == 2
    assert m["mape_included_rows"] == 2
    assert m["mape_nonzero_pct"] == pytest.approx(100 * (0.5 + 0.25) / 2)


def test_nrmse_zero_range():
    r = probability_error_metrics([1, 1, 1], [0.5, 0.6, 0.7])
    assert r.values["nrmse_range"] is None
    assert "range is zero" in r.undefined["nrmse_range"]
    assert r.values["rmse"] is not None


def test_nrmse_equals_rmse_for_binary():
    m = probability_error_metrics([0, 1, 1], [0.2, 0.6, 0.9]).values
    assert m["nrmse_range"] == pytest.approx(m["rmse"])


def test_threshold_boundary_is_inclusive():
    assert apply_threshold([0.49, 0.5, 0.51], 0.5).tolist() == [0, 1, 1]
    r = evaluate_binary([0, 1, 1], [0.49, 0.5, 0.51], threshold=0.5)
    assert r["confusion_matrix"] == {"tn": 1, "fp": 0, "fn": 0, "tp": 2}
    assert r["threshold"] == 0.5


def test_explicit_y_pred_overrides_threshold():
    r = evaluate_binary([0, 1], [0.9, 0.1], y_pred=[0, 1])
    assert r["label_source"] == "explicit y_pred"
    assert r["threshold"] is None
    assert r["metrics"]["accuracy"] == 1
    assert r["metrics"]["roc_auc"] == 0  # ranking still uses probabilities


def test_confusion_matrix_counts():
    y = [1, 1, 1, 0, 0, 0, 0]
    p = [0.9, 0.8, 0.2, 0.7, 0.1, 0.1, 0.3]
    cm = evaluate_binary(y, p, threshold=0.5)["confusion_matrix"]
    assert cm == {"tn": 3, "fp": 1, "fn": 1, "tp": 2}


def test_counts_function_empty_raises():
    with pytest.raises(MetricInputError):
        classification_metrics_from_counts(0, 0, 0, 0)


def test_calibration_bins_cover_all_rows_and_ece():
    y = np.array([0, 1, 1, 0, 1, 1])
    p = np.array([0.0, 0.05, 0.55, 0.5, 0.95, 1.0])
    bins = calibration_bins(y, p, n_bins=10, min_bin_count=2)
    assert sum(b["count"] for b in bins) == 6
    assert bins[0]["count"] == 2 and bins[9]["count"] == 2 and bins[5]["count"] == 2
    assert bins[1]["mean_predicted"] is None and bins[1]["low_count"] is True
    r = evaluate_binary(y, p, threshold=0.5)
    expected = sum(b["count"] / 6 * b["abs_gap"] for b in bins if b["count"])
    assert r["metrics"]["ece"] == pytest.approx(expected)


def test_serialization_of_undefined_metrics_is_strict_json():
    r = evaluate_binary(np.ones(3, dtype=int), np.array([0.2, 0.9, 0.6]))
    text = dumps(r)
    back = json.loads(text)
    assert back["metrics"]["roc_auc"] is None
    assert "roc_auc" in back["undefined"]
    assert "NaN" not in text
    assert json.loads(dumps({"x": np.float64("nan"), "y": np.int64(3)})) == {"x": None, "y": 3}


def test_metadata_passthrough():
    r = evaluate_binary([0, 1], [0.2, 0.8], metadata={"model": "m", "split": "test"})
    assert r["metadata"] == {"model": "m", "split": "test"}


def test_subgroups_small_groups_not_scored():
    y = np.array([0, 1] * 30 + [1, 0])
    p = np.where(y == 1, 0.8, 0.2).astype(float)
    groups = ["a"] * 60 + ["b"] * 2
    rows = {r["group"]: r for r in evaluate_subgroups(y, p, groups, min_samples=50)}
    assert rows["a"]["status"] == "ok" and rows["a"]["metrics"]["accuracy"] == 1
    assert rows["b"]["metrics"] is None and "insufficient" in rows["b"]["status"]
