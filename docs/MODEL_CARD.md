# Model Card — RevenueRescue AI Recovery Predictor

**Model Version:** `rr-lightgbm-optimized.v2`  
**Model Type:** Calibrated Gradient Boosted Decision Tree (LightGBM + Platt Sigmoid Scaling)  
**Task:** Binary Classification (Estimating probability of transaction recovery)  
**Date:** October 26, 2026  
**License:** MIT

---

## 1. Intended & Prohibited Use

### Intended Use Cases:
- **Prioritization & Queue Ranking:** Ordering failed payments and subscription mandate retries by expected recovery probability.
- **Selective Automation:** Automatically executing recovery actions (SMS notification, scheduled retry, payment link dispatch) **only when model confidence exceeds the high-confidence threshold ($\tau = 0.80$, $\ge 91\%$ precision)**.
- **Cost Minimization:** Suppressing futile retries and expensive communication channels when failure causes are permanent (e.g. expired cards, closed accounts).

### Strictly Prohibited Uses:
- **Autonomous Financial Movement:** The model must **never** authorize financial debits or transactions. Authorization is strictly reserved for the deterministic merchant policy engine.
- **Declaring Revenue Recovered:** A high predicted probability must **never** be treated as proof of funds capture. Revenue is counted as recovered only when verified by authoritative payment gateway/banking records.
- **Credit Scoring or Customer Denials:** This model is calibrated strictly for recovery mechanism success; it must never be used for customer underwriting, creditworthiness assessment, or account termination.

---

## 2. Model Performance & Evaluation

Evaluated on the locked held-out test partition ($N = 15,166$ events, baseline prevalence: $62.15\%$):

### Summary Metrics Across Operating Thresholds:
| Evaluation Mode | Threshold ($\tau$) | Precision | Coverage | Recall | Accuracy | ROC-AUC | Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Prior Baseline** | 0.50 | 62.15% | 100.0% | 100.0% | 62.15% | 0.5000 | 0.2353 |
| **Balanced Operating Point** | 0.40 | 63.11% | 97.41% | 98.92% | 63.39% | 0.6675 | 0.2140 |
| **Standard Classification** | 0.50 | 65.69% | 82.45% | 87.03% | 64.03% | 0.6675 | 0.2136 |
| **High-Precision Tier** | 0.70 | 79.95% | 27.61% | 35.56% | 58.12% | 0.6675 | 0.2136 |
| **High-Confidence Operating Point** | **0.80** | **91.06%** | **12.69%** | **18.59%** | **52.41%** | **0.6675** | **0.2136** |

### Statistical Bootstrapping (95% Confidence Intervals):
- **ROC-AUC:** `[0.6586, 0.6764]`
- **PR-AUC (Average Precision):** `[0.7735, 0.7909]`
- **High-Confidence Precision ($\tau=0.80$):** `[89.65%, 92.42%]`

---

## 3. Precision-Coverage Tradeoff & 90% Precision Finding

An empirical analysis of whether **90% precision** is achievable yielded the following findings:

1. **Achievable at Useful Coverage:** At threshold $\tau \ge 0.80$, the model achieves **91.06% precision** across **1,924 test transactions (12.69% coverage)**.
2. **Scenario Breakdown:**
   - **`FAILED_PAYMENT`:** **91.34% precision** at 15.82% coverage.
   - **`FAILED_SUBSCRIPTION`:** **90.46% precision** at 15.73% coverage.
   - **`GATEWAY_TEMPORARY` (Technical Glitches):** **90.99% precision** at >95% coverage.
   - **`CHECKOUT_ABANDONED`:** 0.0% coverage at $\tau = 0.80$. Because baseline checkout recovery is 53.91% and highly stochastic, the calibrated model correctly refuses to assign high confidence, preventing costly automated overreach.

---

## 4. Calibration & Uncertainty

The base LightGBM estimator outputs raw log-odds which can be uncalibrated under extreme leaf assignments.
- We apply **Platt Sigmoid Calibration** (`CalibratedClassifierCV(method='sigmoid')`) fitted exclusively on the validation partition.
- Post-calibration **Brier score is 0.2136** (vs 0.2353 prior baseline), confirming well-calibrated posterior probabilities.

---

## 5. Known Risks, Failure Modes & Monitoring Requirements

1. **Drift in Gateway Decline Codes:** When banking networks or payment processors alter internal decline mappings, prediction probabilities may shift.
2. **Distribution Shift:** Model was trained on synthetic transaction logs. Production deployment requires shadow-mode validation against live merchant transaction feeds.
3. **Fallback Policy:** If `MLScoringService` encounters missing features, unparseable payloads, or inference latency > 50ms, it immediately falls back to deterministic rule scoring without interrupting transaction processing.
