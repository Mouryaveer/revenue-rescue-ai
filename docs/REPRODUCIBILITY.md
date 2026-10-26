# Reproducibility Guide — RevenueRescue AI

This guide provides instructions to reproduce all data engineering, distributed analytics, machine learning benchmarks, and test suites from a clean environment.

---

## 1. System Requirements

- **Operating System:** Linux, macOS, or Windows (with Python 3.11 / 3.12)
- **Java Runtime:** Java 17+ or Java 21/24 (required for PySpark 4.2.0)
- **Memory:** Minimum 8 GB RAM (16 GB recommended)
- **Disk:** ~2 GB free disk space

---

## 2. Environment Setup

```bash
# 1. Clone repository
git clone https://github.com/Mouryaveer/revenue-rescue-ai.git
cd revenue-rescue-ai

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 4. Install dependencies
pip install -r backend/requirements.txt
pip install pyspark==4.2.0 ruff==0.7.1 mypy==1.13.0 bandit==1.8.0
```

---

## 3. End-to-End Execution Commands

### Step 1: Data Validation & Preprocessing (Pandas Pipeline)
Validates the 100,000 raw events and generates point-in-time features with zero data leakage:
```bash
python -m pipeline.pandas_preprocessor
```
*Expected Output:* `data/preprocessed/events_clean.parquet` and `data/preprocessed/preprocessing_manifest.json`.

---

### Step 2: PySpark Distributed ETL & Spark SQL Analytics
Executes distributed window transformations and runs Spark SQL analytics:
```bash
python -m pipeline.spark_pipeline
```
*Expected Output:*
- Partitioned dataset: `data/spark_processed/events_partitioned.parquet/` (partitioned by `chrono_split`)
- Analytics report: `data/spark_processed/spark_analytics_report.json`

---

### Step 3: Run Big Data Performance Benchmark (Pandas vs PySpark)
Executes comparative cold/warm execution benchmarks and verifies aggregation correctness:
```bash
python scripts/benchmark_spark_pandas.py
```
*Expected Output:*
- `reports/benchmarks/benchmark_spark_pandas.json`
- `reports/benchmarks/benchmark_spark_pandas.md`

---

### Step 4: Train & Evaluate Machine Learning Models
```bash
# 1. Train LightGBM Tabular Production Model
python scripts/train_lightgbm.py

# 2. Inspect Hybrid Research Notebook (or run headless via jupyter)
jupyter nbconvert --to notebook --execute Notebooks/RevenueRescue_AI_Data_Preprocessing.ipynb
jupyter nbconvert --to notebook --execute Notebooks/RevenueRescue_AI_LightGBM_Transformer_Collab.ipynb
```
*Expected Output:*
- `models/artifacts/lightgbm_recovery_model.joblib`
- `models/artifacts/hybrid_metadata.json`
- `models/artifacts/evaluation_report.json`

---

### Step 5: Execute Complete Test & Quality Suite
```bash
# 1. Code Style and Linting (0 errors expected)
ruff check .
ruff format --check .

# 2. Static Type Checking (0 errors expected)
mypy backend/app agents policies simulator --ignore-missing-imports

# 3. Security Scan (0 errors expected)
bandit -s B101,B311 -r backend/app agents policies simulator -x tests,agents/tests,policies/tests,simulator/tests

# 4. Run All 197 Automated Unit & Integration Tests
pytest -v
```

---

## 4. Seeds & Determinism

| Component | Random Seed | Behavior |
| :--- | :--- | :--- |
| **Synthetic Event Generator** | `SEED = 42` | Generates identical 100,000 transaction events |
| **Chronological Split** | Deterministic Quantiles | Splits at 70% and 85% timestamps |
| **LightGBM Classifier** | `random_state = 42` | Deterministic tree construction |
| **PyTorch Transformer** | `torch.manual_seed(42)` | Deterministic weight initialization |
| **Payment Simulator** | Seeded per test run | Deterministic recovery outcomes |
