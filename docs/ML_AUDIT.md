# ML, Evaluation and Big Data Audit (2026-10-29)

Audit performed before the evaluation upgrade described in
`.kiro/specs/ml-evaluation-upgrade/`. Every finding below was observed in this repository with a
command or file read; the evidence column says where.

## Baseline

| Item | Observed |
|---|---|
| Branch | `main`, 4 commits ahead of `origin/main` (head `fdece48`) |
| Uncommitted work | Both notebooks modified (not by this upgrade), `scripts/verify_all_notebooks.py` and `.kiro/collab/` untracked. Notebooks backed up to `backups/notebooks_20261029_pre_upgrade/` (gitignored). |
| Tests | `pytest` → **231 passed**, 84 s |
| Ruff | 7 findings, all in untracked `scripts/verify_all_notebooks.py` |
| Environment | Python 3.11.9 `.venv`; pandas 2.2.3, numpy 1.26.4, scikit-learn 1.5.2, LightGBM 4.5.0, torch 2.5.1+cpu, PySpark 4.2.0 (requirements file pins 3.5.8), Java 24 |

## Sources of truth (before the upgrade)

| Concern | Source | Note |
|---|---|---|
| Raw data | `data/training/payment_events.csv` | 100,000 synthetic events, 63,154 customers, target `recovered` (61.99% positive) |
| Supplied split | `split` column / `train.csv`, `validation.csv`, `test.csv` | **Random**: all three splits span the same Jan–May period |
| Chronological split | `chrono_split` in `data/preprocessed/events_clean.parquet` | 70/15/15 by timestamp, produced by the preprocessing notebook |
| Feature schema | `data/preprocessed/feature_spec.json` (`rr-features.v2`) | 5 categorical + 12 numeric (8 point-in-time history features) |
| Model served by the API | `models/artifacts/lightgbm_recovery_model.joblib` (`rr-lightgbm.v1`, 2026-10-14) | Trained by `scripts/train_lightgbm.py` on the **random** split |
| Models quoted in README | Notebook hybrid run | Numbers do not match any saved artifact (see D3) |

## Defects and risks

| ID | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| D1 | High | The served model (`rr-lightgbm.v1`) was trained and evaluated on the random supplied split, uses `event_month_utc` (test months 4–5 vs train months 1–4 under a forward split) and `class_weight="balanced"`, which shifts probabilities (10-bin ECE 0.105). | `scripts/train_lightgbm.py`, `models/artifacts/evaluation_report.json` | Replace with a model trained on `chrono_split`, no month feature, unweighted, validation-selected threshold. |
| D2 | High | Training/serving skew: callers (`recovery_service.py`, `deterministic_nodes.py`) never pass a timestamp, payment method, device or country. `MLScoringService` substitutes hour 12, weekday 0, month 1, `card`, `web`, `IN`, so every served prediction uses fabricated inputs. | `backend/app/services/recovery_service.py:117-126`, `agents/nodes/deterministic_nodes.py:62-70`, `ml_scoring_service.py:_prepare_feature_row` | Missing inputs become missing values (LightGBM handles NaN natively); derive hour/weekday from `occurred_at` when provided; report which inputs were missing. |
| D3 | High | Three model generations coexist. README reports LightGBM ROC-AUC 0.6676 and a 90/10 hybrid; `hybrid_metadata.json` (latest run) reports 0.6640 and an 80/20 blend; the API serves a third model. | `README.md:145-151`, `models/artifacts/hybrid_metadata.json` | One canonical evaluation report; README numbers generated from it; consistency check script. |
| D4 | Medium | Metric formulas are duplicated in `train_lightgbm.py`, `ml_optimization_suite.py` and the notebook, with different definitions. Undefined values are converted to numbers: specificity → 0.0, precision with no selections → 1.0. MCC, Cohen's kappa, specificity (notebook), and all probability-error metrics are missing. | the three files | Central `evaluation/metrics.py`; undefined metrics return `null` with a reason. |
| D5 | Medium | `ml_optimization_suite.py` uses the random split, fits the Platt calibrator on validation and reports validation metrics of the calibrated model on the same rows. | `scripts/ml_optimization_suite.py` | Keep as a labelled legacy experiment; canonical pipeline uses chrono split, and calibration is compared on validation via cross-fitting only. |
| D6 | Medium | Notebook stored outputs contain errors (`ModuleNotFoundError: matplotlib` in the preprocessing notebook, `ImportError: pyarrow` in the ML notebook) — the notebooks were last run on a kernel without the project dependencies. | stored cell outputs | Re-execute both notebooks on the `.venv` kernel with nbclient and verify no error outputs. |
| D7 | High | Spark derives `event_hour_utc` in the JVM session time zone (`Asia/Calcutta` on this machine): `2026-05-15T01:41:00Z` → hour 7. Spark and Pandas hour/weekday features disagree. | `spark_pipeline.py` + probe run (`hour=7`) | Set `spark.sql.session.timeZone=UTC`; parity test. |
| D8 | Medium | Spark split cut-offs use `approxQuantile` while Pandas uses an interpolated exact quantile; boundaries can differ. | `spark_pipeline.py:transform`, `pandas_preprocessor.py:transform` | Shared rank-based cut-off definition, computed exactly in both engines; parity test. |
| D9 | Medium | Benchmark correctness compares only `total_events` per event type; the Markdown hardcodes "MATCH" and "Verified", and claims column pruning and Pandas OOM at 100M rows without measurement. Spark memory is not measured. | `scripts/benchmark_spark_pandas.py` | Compare engineered features and aggregates with tolerances; report plan observations parsed from the actual plan; remove unmeasured claims. |
| D10 | Low | Spark reads with a schema but does not validate categories, nulls or non-positive amounts; the Spark test fixture uses failure reasons that the Pandas validator rejects. | `spark_pipeline.py`, `tests/data_pipeline/test_spark_pipeline.py` | Validation step with clear errors. |
| D11 | Medium | Preprocessing logic exists twice (notebook cells and `PandasPreprocessor`), and the module writes `supplied_split_is_time_overlapping: True` as a constant. | `pandas_preprocessor.py` | Notebook calls the module; the flag is computed. |
| D12 | Low | Leakage audit is name-based only; nothing re-verifies that history features exclude later events. | `pipeline/leakage_audit.py` | Brute-force point-in-time recomputation check on a sample. |
| D13 | Info | Timestamps have minute resolution; 39,428 rows share a timestamp with another row; 2 rows share both customer and timestamp. Ties are broken by `event_id`. Split cut-offs use `<`, so equal timestamps never straddle a split. | probe script | Documented; tie rule tested. |
| D14 | Info | The policy engine's `AuthorizationContext` contains no model probability, so ML output cannot authorise an action by construction. No test pins this. | `policies/engine/policy_engine.py` | Regression test: high probability + denied action stays denied. |

## Claims that were not supported by evidence

- "No data leakage" in `train_lightgbm.py` and the evaluation report: true for preprocessing fit, but the split was random (D1).
- "Exact count & recovery rate match" in the benchmark report: only counts were compared (D9).
- "Hybrid (90% LGBM / 10% Trans)" in the README: the saved metadata says 80/20 (D3).
- `verify_all_notebooks.py` prints success based on stored outputs that contain errors (D6).

## Decisions

1. **Canonical split:** `chrono_split` (train < 70th, validation < 85th percentile of time, test after). The supplied random split is kept only as a labelled comparison.
2. **Canonical production model:** decided from the canonical run. The previous run showed the no-history LightGBM ablation matching the full model on test ROC-AUC (0.6643 vs 0.6640), and history features cannot be computed by the serving path today. If the new run confirms this, the served model uses the no-history feature set.
3. **Transformer and hybrid:** kept as research experiments in the notebook; served only if they show an improvement beyond bootstrap uncertainty.
