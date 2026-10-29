# Requirements: ml-evaluation-upgrade

Source: master engineering prompt of 2026-10-28. Audit: `docs/ML_AUDIT.md`.

## R1 Centralised metrics
`evaluation/metrics.py` computes probability-error metrics (MSE, RMSE, MAE, MAPE on non-zero
targets, R², NRMSE by range, MedAE, mean error), classification metrics (accuracy, precision,
recall, F1, specificity, ROC-AUC, log loss, MCC, Cohen's kappa, balanced accuracy) and
complements (PR-AUC, Brier, confusion matrix, FPR, FNR, NPV, support, coverage, calibration bins).
Invalid input raises `MetricInputError`; undefined metrics return `None` with a reason.

## R2 Evaluation protocol
Train fits models, validation selects thresholds/weights/calibration, test is scored once.
Threshold report on validation, independent test report, bootstrap CIs, baselines.

## R3 Canonical report
`reports/evaluation/latest.{json,md}`, `metrics_by_model.csv`, `threshold_analysis.csv`,
`calibration.csv`, figures; with dataset fingerprint, feature version, environment, seed. A failed
run must not overwrite the canonical report.

## R4 Big data
Spark uses UTC, validated schema, the same split cut-off rule and feature definitions as Pandas;
parity tests on rows, features and aggregates; benchmark reports measured values only.

## R5 Serving
One model bundle with feature version, categories, threshold; incompatible bundles fail loudly
(no silent fallback to an unrelated artifact); missing inputs are reported, not invented.

## R6 Safety
ML probability cannot override a policy denial (regression test).

## R7 Notebooks
Both notebooks use the shared modules, execute top-to-bottom on the project kernel without errors.

## R8 Documentation and consistency
README, model card and evaluation docs generated from or checked against the canonical report.
