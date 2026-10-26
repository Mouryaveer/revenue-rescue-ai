# Notebooks: audit, fixes and executed results

Both notebooks in `Notebooks/` were rewritten and **executed locally** on `data/training/`
(`synthetic-payment-events.v1`: 100,000 events, all synthetic). The environment was Python 3.11.9,
pandas 2.2.3, LightGBM 4.5.0 and torch 2.5.1+cpu. Executed outputs are saved in the `.ipynb` files.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
cd Notebooks
..\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --inplace RevenueRescue_AI_Data_Preprocessing.ipynb
..\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --inplace RevenueRescue_AI_LightGBM_Transformer_Collab.ipynb
# optional: rerun the models on the supplied (random) split
$env:RR_SPLIT_COL="supplied_split"; ..\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --output model_supplied.ipynb RevenueRescue_AI_LightGBM_Transformer_Collab.ipynb
```

Runtime on CPU: preprocessing takes about 20 s. The model notebook takes about 4.5 min, of which the Transformer is about 180 s.

## Problems found and fixed

| # | Issue | Evidence | Fix |
| --- | --- | --- | --- |
| 1 | Hard-coded Colab path; the notebooks had never been executed | `DATA_DIR = Path("/content")`, no outputs | Data folder auto-located (or set via `RR_DATA_DIR`); executed locally |
| 2 | Supplied split is random, not time-ordered | train, validation and test all span 2026-01-01 → 2026-05-19 | New primary `chrono_split` (70/15/15, strictly ordered by time); supplied split kept for comparison |
| 3 | `customer_profiles.csv` cannot be joined | 0 of 63,154 event customers match (`CUST-00001` vs `CUST-00083811` ID formats) | Not joined |
| 4 | `customer_history_features.csv` leaks the label | Single-feature train AUC: `previous_recovery_rate` 0.948, `success_count` 0.818, `has_recovered` 0.774 | Not joined. Replaced by point-in-time history computed from earlier events' input fields (no labels) |
| 5 | Transformer sequences ignored a customer's earlier events in other splits | Sequences were grouped within each split | All earlier events of the customer are used, from any split (inputs only, no labels) |
| 6 | Transformer saw one-hot vectors with no time information | Each event was one-hot encoded and fed through a linear layer | Categorical embeddings, scaled numerics, a time-gap feature (log1p of hours), positional embedding and padding mask |
| 7 | LightGBM always trained 500 trees and used one-hot encoding | `n_estimators=500` | Native categorical features; early stopping on validation log loss (stopped at 137 trees) |
| 8 | Fixed 0.5 decision threshold | With 62% positives, F1-tuning predicts every case positive (the constant baseline scores F1 0.766) | Threshold maximizes TPR − FPR (Youden's J) on validation, then frozen for test |
| 9 | No baselines to compare against | — | Prior-rate and rule baselines (smoothed recovery rate per `event_type × failure_reason`); bootstrap 95% CIs |
| 10 | Month and day-of-month used as features | Test-period values never occur in training | Dropped; only hour and day-of-week kept |
| 11 | Required metrics missing | — | Added log loss, PR-AUC, confusion counts, per-segment AUC, calibration table, latency and model size |
| 12 | CSV exports; saved models never reloaded | — | Parquet with checksums; saved models reloaded and checked to give identical predictions |

## Results: held-out test, chronological split, seed 42

| Model | ROC-AUC (95% CI) | PR-AUC | Log loss | Brier |
| --- | --- | --- | --- | --- |
| Prior baseline | 0.5000 | 0.6207 | 0.6637 | 0.2354 |
| Rule baseline | 0.6383 [0.6299, 0.6466] | 0.7410 | 0.6203 | 0.2171 |
| LightGBM | 0.6640 [0.6551, 0.6719] | 0.7773 | 0.6130 | 0.2145 |
| LightGBM, no history features | 0.6643 [0.6560, 0.6717] | 0.7776 | 0.6128 | 0.2145 |
| Transformer Encoder | 0.6628 [0.6542, 0.6708] | 0.7769 | 0.6139 | 0.2149 |
| Hybrid (LightGBM weight 0.80, chosen on validation) | 0.6648 [0.6558, 0.6727] | 0.7781 | 0.6127 | 0.2144 |

On the supplied random split: rule baseline 0.6386, LightGBM 0.6676, Transformer 0.6639, hybrid 0.6676 ROC-AUC. Re-running the notebook reproduced the chronological results exactly.

By segment (hybrid test AUC): FAILED_PAYMENT 0.690, FAILED_SUBSCRIPTION 0.674, CHECKOUT_ABANDONED 0.553.
Calibration is good where there is data: in the largest probability bin the mean prediction is 0.546 against an observed rate of 0.556.
Model size: the Transformer has 111,425 parameters and early-stopped after 8 epochs; LightGBM has 137 trees.
Single-row CPU latency: LightGBM about 12 ms, Transformer about 5 ms.

## Interpretation

- Both learned models beat the rule baseline by about 0.026 AUC, with non-overlapping confidence intervals, and have lower log loss (0.613 vs 0.620).
  The gain is modest: `failure_reason` alone provides 69% of LightGBM's split gain.
- The hybrid is not significantly better than LightGBM alone (AUC 0.6648 vs 0.6640, overlapping CIs).
  The Transformer does not beat LightGBM, and removing the history features changes nothing. Customers average
  only 1.5 events each, so this dataset has almost no sequential signal. These results do not support claiming
  that the sequence model adds value.
- Checkout abandonment is close to unpredictable with the available fields (AUC 0.553).
- All metrics are measured on a synthetic label. They are not recovered revenue.

## Artifacts

These folders are git-ignored; regenerate them by running the notebooks.

- `data/preprocessed/`: `events_clean.parquet`, `feature_spec.json` (`rr-features.v2`), `preprocessing_manifest.json`, `leakage_audit.csv`, `output_checksums.csv`
- `models/artifacts/`: `lightgbm.txt`, `transformer.pt`, `hybrid_metadata.json` (`rr-hybrid.v1`, includes the metrics above), `test_predictions.parquet`

The backend and the LangGraph agent do not load these artifacts yet. Adding an ML prediction node is planned for Phase 11.
