# Machine Learning Training Guide — RevenueRescue AI

## 1. Overview & Model Architecture

RevenueRescue AI develops predictive models to estimate the probability of recovering revenue from a payment failure, subscription mandate issue, or checkout abandonment.

| Property | Standalone Operational Pipeline | Research Hybrid Pipeline |
| :--- | :--- | :--- |
| **Model Version** | `rr-lightgbm.v1` | `rr-hybrid.v1` |
| **Frameworks** | LightGBM 4.5.0 + scikit-learn 1.5.2 | LightGBM 4.5.0 + PyTorch 2.5.1 |
| **Primary Script / Notebook**| `scripts/train_lightgbm.py` | `Notebooks/RevenueRescue_AI_LightGBM_Transformer_Collab.ipynb` |
| **Artifacts** | `lightgbm_recovery_model.joblib` | `lightgbm.txt`, `transformer.pt`, `hybrid_metadata.json` |
| **Inference Runtime** | In-process CPU via `MLScoringService` | In-process PyTorch + LightGBM C++ API |
| **Evaluation Data** | Held-out 15,166 synthetic events | Chronological held-out 15,000 synthetic events |

---

## 2. Training Pipelines

### 2.1 Standalone Production Pipeline (`scripts/train_lightgbm.py`)
This pipeline builds a deployable scikit-learn compatible pipeline serialized with `joblib`:
1. **Preprocessing:** `ColumnTransformer` with `OneHotEncoder(handle_unknown='ignore')` for categoricals and `SimpleImputer(strategy='median')` + `StandardScaler()` for numerics.
2. **Estimator:** `LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42)`.
3. **Early Stopping:** Evaluated on `data/training/validation.csv` with 20 rounds patience.
4. **Export Artifacts:**
   - `models/artifacts/lightgbm_recovery_model.joblib`
   - `models/artifacts/metadata.json`
   - `models/artifacts/feature_order.json`
   - `models/artifacts/evaluation_report.json`

**Command to run:**
```bash
python scripts/train_lightgbm.py
```

### 2.2 Research Hybrid Pipeline (`RevenueRescue_AI_LightGBM_Transformer_Collab.ipynb`)
This notebook investigates sequence-aware temporal dynamics:
1. **LightGBM Native:** Trains directly on native pandas categorical dtypes.
2. **Transformer Encoder:**
   - Orders all events chronologically per customer up to `max_len=8`.
   - Embeds categorical tokens (`event_type`, `failure_reason`, `payment_method`, `device_type`, `country`) into a 64-dimensional space.
   - Passes right-aligned customer sequences through a 2-layer Transformer Encoder (`nhead=4`, `dim_feedforward=128`, `dropout=0.1`).
   - Mean-pools token representations across valid unpadded tokens.
3. **Hybrid Fusion:**
   - Evaluates linear combination: $P_{\text{hybrid}} = w \cdot P_{\text{LGBM}} + (1 - w) \cdot P_{\text{Transformer}}$.
   - Validation grid search selects optimal weights based on validation log loss: **$w=0.90$ LightGBM, $0.10$ Transformer**.

---

## 3. History-Feature Ablation Findings

The evaluation protocol explicitly tested LightGBM with and without historical customer features (`cust_prior_*` and `hours_since_prev_event`):

| Model Configuration | Test ROC-AUC | Test PR-AUC | Test Log Loss | 95% Confidence Interval |
| :--- | :--- | :--- | :--- | :--- |
| **LightGBM (with history features)** | **0.6676** | **0.7812** | **0.6106** | `[0.6585, 0.6757]` |
| **LightGBM (no history features)** | **0.6676** | **0.7822** | **0.6103** | `[0.6588, 0.6759]` |

### Technical Analysis:
The 95% bootstrap confidence intervals overlap completely. History features do not provide statistically significant improvement on this synthetic dataset. In the synthetic data generator, transaction outcomes are largely determined by immediate event characteristics (`failure_reason`, `event_type`, `retry_count`, `amount_paise`) rather than persistent multi-month customer states. This negative finding is documented to ensure academic transparency.

---

## 4. Operational Invariant

> [!IMPORTANT]
> The ML model outputs a **conditional probability estimate**, not an authorization.
> - The Agent uses this probability strictly for ranking recovery interventions.
> - The Deterministic Policy Engine independently authorizes or blocks all actions.
> - The Recovery Verifier independently confirms whether revenue was actually captured.
