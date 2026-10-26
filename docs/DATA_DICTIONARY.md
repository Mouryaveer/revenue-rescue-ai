# Data Dictionary — RevenueRescue AI

**Schema Version:** `rr-features.v2`  
**Dataset Version:** `synthetic-payment-events.v1`  
**Currency Unit:** `paise` (1 INR = 100 paise; avoids floating-point rounding errors in financial transactions)

---

## 1. Raw Event Schema (`payment_events.csv`)

| Column Name | Data Type | Nullable | Description & Domain Values |
| :--- | :--- | :--- | :--- |
| `schema_version` | String | No | Format version identifier (e.g. `payment-event.v1`). |
| `event_id` | String | No | Globally unique identifier per transaction event (e.g. `EVT-000000000001`). Primary key. |
| `event_type` | String | No | High-level risk event category: `FAILED_PAYMENT`, `FAILED_SUBSCRIPTION`, `CHECKOUT_ABANDONED`. |
| `customer_id` | String | No | Pseudonymous customer identifier (e.g. `CUST-00083811`). Used for customer history grouping. |
| `amount_paise` | BigInt | No | Gross transaction value in Indian paise (e.g. `704908` = ₹7,049.08). Invariant: must be > 0. |
| `currency` | String | No | ISO 4217 currency code. Constant `INR` in this benchmark. |
| `failure_reason` | String | No | Technical decline reason: `INSUFFICIENT_FUNDS`, `BANK_DECLINE`, `AUTH_FAILURE`, `GATEWAY_TEMPORARY`, `EXPIRED_METHOD`, `MANDATE_FAILURE`, `SUBSCRIPTION_GRACE`, `CHECKOUT_ABANDONED`, `UNKNOWN`. |
| `occurred_at` | Timestamp | No | ISO-8601 UTC timestamp of event occurrence (e.g. `2026-05-15T01:41:00Z`). |
| `payment_method` | String | Yes | Instrument used: `card`, `upi`, `netbanking`, `wallet`. |
| `device_type` | String | Yes | Channel context: `web`, `android`, `ios`. |
| `country` | String | Yes | Country code: `IN`, `US`, `GB`, `AU`, `SG`. |
| `retry_count` | Integer | No | Count of attempts already executed prior to this event (0 to 3). |
| `recovered` | Boolean | No | Ground-truth outcome target: `True` if successfully recovered in simulation; `False` otherwise. |
| `is_synthetic` | Boolean | No | Invariant marker indicating data was generated synthetically. Constant `True`. |
| `split` | String | Yes | Random split assignment in raw file: `train`, `validation`, `test`. |

---

## 2. Feature Specification (`rr-features.v2`)

Features used for LightGBM tabular training and Transformer sequence construction.

### Categorical Features (5)
- `event_type`: Categorical with 3 levels.
- `failure_reason`: Categorical with 8 levels.
- `payment_method`: Categorical with 4 levels.
- `device_type`: Categorical with 3 levels.
- `country`: Categorical with 5 levels.

### Numeric & Temporal Features (12)
- `amount_paise`: Transaction value in paise.
- `retry_count`: Prior retry attempts (0, 1, 2, 3).
- `event_hour_utc`: Hour of day in UTC (0–23).
- `event_dayofweek_utc`: Day of week in UTC (0 = Monday, 6 = Sunday).
- `cust_prior_events`: Number of historical events for this customer prior to this timestamp.
- `cust_prior_amount_mean`: Mean amount in paise of customer's prior attempts (`NaN` if first event).
- `cust_prior_retry_total`: Sum of retry counts across prior events.
- `cust_prior_checkout_abandoned`: Prior checkout abandonments by this customer.
- `cust_prior_failed_payment`: Prior payment failures by this customer.
- `cust_prior_failed_subscription`: Prior subscription failures by this customer.
- `cust_prior_same_failure_reason`: Count of prior events for this customer with the identical failure reason.
- `hours_since_prev_event`: Time elapsed (hours) since the customer's previous event (`NaN` if first event).

---

## 3. Excluded Fields (Data Leakage & Lineage Protection)

| Field Name | Reason for Exclusion from Model Features |
| :--- | :--- |
| `recovered` | **Target label.** Including this in features would cause trivial target leakage. |
| `event_id` | **High-cardinality identifier.** Used for lineage only; does not generalize across transactions. |
| `customer_id` | **Customer identity.** Excluded from features to prevent memorization and ensure generalized scoring across new merchants/customers. |
| `occurred_at` | Raw timestamp string; decomposed into `event_hour_utc` and `event_dayofweek_utc`. |
| `currency` | Constant (`INR`) in dataset; zero variance. |
| `is_synthetic` | Constant (`True`); zero variance. |
| `schema_version` | Constant metadata; zero variance. |
| `chrono_split` / `supplied_split` | Split metadata; never available at runtime. |
