"""
Train LightGBM tabular recovery predictor on synthetic payment events.

Requirements:
- Strict prevention of target leakage, customer history leakage, and preprocessing leakage.
- Preprocessing fit ONLY on training data.
- Validation split used for tuning/monitoring; test split evaluated once at the end.
- Persists model artifact, feature order, training metadata, and evaluation report.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42
TARGET = "recovered"

CATEGORICAL_FEATURES = [
    "event_type",
    "failure_reason",
    "payment_method",
    "device_type",
    "country",
]

NUMERIC_FEATURES = [
    "amount_paise",
    "retry_count",
    "event_hour_utc",
    "event_dayofweek_utc",
    "event_month_utc",
]

FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract leak-free feature dataframe with consistent column order and derived time features."""
    x = df.copy()
    if "occurred_at" in x.columns:
        ts = pd.to_datetime(x["occurred_at"], errors="coerce", utc=True)
        x["event_hour_utc"] = ts.dt.hour.fillna(12).astype(int)
        x["event_dayofweek_utc"] = ts.dt.dayofweek.fillna(0).astype(int)
        x["event_month_utc"] = ts.dt.month.fillna(1).astype(int)
    else:
        x["event_hour_utc"] = 12
        x["event_dayofweek_utc"] = 0
        x["event_month_utc"] = 1

    # Fill defaults for missing feature columns if any
    for col in CATEGORICAL_FEATURES:
        if col not in x.columns:
            x[col] = "UNKNOWN"
        else:
            x[col] = x[col].fillna("UNKNOWN").astype(str)

    for col in NUMERIC_FEATURES:
        if col not in x.columns:
            x[col] = 0
        else:
            x[col] = pd.to_numeric(x[col], errors="coerce").fillna(0)

    return x[FEATURE_COLUMNS]


def evaluate_predictions(y_true: np.ndarray, y_prob: np.ndarray, threshold: float = 0.50) -> dict:
    """Compute standard classification, discrimination, and calibration metrics."""
    y_pred = (y_prob >= threshold).astype(int)

    # Calculate expected calibration error (ECE) with 10 bins
    bins = np.linspace(0.0, 1.0, 11)
    bin_indices = np.digitize(y_prob, bins) - 1
    ece = 0.0
    for i in range(10):
        mask = bin_indices == i
        if np.any(mask):
            bin_acc = np.mean(y_true[mask])
            bin_conf = np.mean(y_prob[mask])
            bin_size = np.sum(mask)
            ece += (bin_size / len(y_true)) * abs(bin_acc - bin_conf)

    return {
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "average_precision": round(float(average_precision_score(y_true, y_prob)), 4),
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 4),
        "ece_10bin": round(float(ece), 4),
        "threshold": threshold,
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "positive_rate_actual": round(float(np.mean(y_true)), 4),
        "positive_rate_predicted": round(float(np.mean(y_pred)), 4),
    }


def train_and_evaluate(
    data_dir: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    train_path = data_dir / "train.csv"
    val_path = data_dir / "validation.csv"
    test_path = data_dir / "test.csv"
    manifest_path = data_dir / "training_manifest.json"

    if not (train_path.exists() and val_path.exists() and test_path.exists()):
        raise FileNotFoundError(f"Missing one or more required splits in {data_dir}")

    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )

    print(f"Loading data from {data_dir}...")
    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    print(f"Splits loaded: train={len(train_df):,}, val={len(val_df):,}, test={len(test_df):,}")

    # Extract leak-free features
    X_train = extract_features(train_df)
    y_train = train_df[TARGET].astype(int).to_numpy()

    X_val = extract_features(val_df)
    y_val = val_df[TARGET].astype(int).to_numpy()

    X_test = extract_features(test_df)
    y_test = test_df[TARGET].astype(int).to_numpy()

    # Preprocessor fit ONLY on training set
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                NUMERIC_FEATURES,
            ),
        ],
        remainder="drop",
    )

    print("Fitting preprocessor on training data...")
    preprocessor.fit(X_train)
    X_train_trans = preprocessor.transform(X_train)
    X_val_trans = preprocessor.transform(X_val)
    X_test_trans = preprocessor.transform(X_test)

    # Train LightGBM classifier
    print("Training LightGBM model...")
    model = LGBMClassifier(
        objective="binary",
        n_estimators=350,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=1.0,
        class_weight="balanced",
        random_state=SEED,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(
        X_train_trans,
        y_train,
        eval_set=[(X_val_trans, y_val)],
        eval_names=["validation"],
    )

    # Evaluate predictions
    val_probs = model.predict_proba(X_val_trans)[:, 1]
    test_probs = model.predict_proba(X_test_trans)[:, 1]
    train_probs = model.predict_proba(X_train_trans)[:, 1]

    train_metrics = evaluate_predictions(y_train, train_probs)
    val_metrics = evaluate_predictions(y_val, val_probs)
    test_metrics = evaluate_predictions(y_test, test_probs)

    print("Validation metrics:", json.dumps(val_metrics, indent=2))
    print("Held-out test metrics:", json.dumps(test_metrics, indent=2))

    # Feature importance
    feature_names = preprocessor.get_feature_names_out()
    importances = model.feature_importances_
    top_features = sorted(
        [
            {"feature": str(f), "importance": int(imp)}
            for f, imp in zip(feature_names, importances, strict=False)
        ],
        key=lambda x: x["importance"],
        reverse=True,
    )[:20]

    # Save artifacts
    bundle = {
        "model_version": "rr-lightgbm.v1",
        "preprocessor": preprocessor,
        "model": model,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "feature_columns": FEATURE_COLUMNS,
        "created_at": datetime.now(UTC).isoformat(),
        "random_seed": SEED,
    }

    joblib_path = output_dir / "lightgbm_recovery_model.joblib"
    joblib.dump(bundle, joblib_path)
    print(f"Saved model bundle to {joblib_path}")

    # Save feature order
    feature_order_data = {
        "model_version": "rr-lightgbm.v1",
        "target": TARGET,
        "feature_columns": FEATURE_COLUMNS,
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "expected_dtypes": {
            "event_type": "str",
            "failure_reason": "str",
            "payment_method": "str",
            "device_type": "str",
            "country": "str",
            "amount_paise": "int",
            "retry_count": "int",
            "event_hour_utc": "int",
            "event_dayofweek_utc": "int",
            "event_month_utc": "int",
        },
    }
    (output_dir / "feature_order.json").write_text(
        json.dumps(feature_order_data, indent=2), encoding="utf-8"
    )

    # Save metadata
    metadata = {
        "model_version": "rr-lightgbm.v1",
        "model_type": "LightGBM Binary Classifier (LGBMClassifier)",
        "dataset_version": manifest.get("dataset_version", "synthetic-payment-events.v1"),
        "all_data_is_synthetic": True,
        "target": TARGET,
        "rows": {
            "train": len(train_df),
            "validation": len(val_df),
            "test": len(test_df),
        },
        "training_timestamp_utc": datetime.now(UTC).isoformat(),
        "random_seed": SEED,
        "features": FEATURE_COLUMNS,
        "top_features": top_features,
        "interpretation": "Trained on synthetic payment events for zero-cost decision support. Operational recovery confirmation remains verifier-authoritative.",
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Save evaluation report
    report = {
        "model_version": "rr-lightgbm.v1",
        "dataset_version": manifest.get("dataset_version", "synthetic-payment-events.v1"),
        "evaluation_timestamp_utc": datetime.now(UTC).isoformat(),
        "metrics": {
            "train": train_metrics,
            "validation": val_metrics,
            "held_out_test": test_metrics,
        },
    }
    (output_dir / "evaluation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    # Save markdown summary
    report_md = (
        f"""# LightGBM Recovery Predictor — Model Evaluation Report

- **Model Version:** rr-lightgbm.v1
- **Dataset Version:** {manifest.get('dataset_version', 'synthetic-payment-events.v1')}
- **Dataset Nature:** 100% Synthetic Payment Events (no real cardholder PII)
- **Training Timestamp (UTC):** {datetime.now(UTC).isoformat()}
- **Random Seed:** {SEED}

## Split Sizes & Target Distribution
- **Train:** {len(train_df):,} rows (actual positive rate: {train_metrics['positive_rate_actual']:.2%})
- **Validation:** {len(val_df):,} rows (actual positive rate: {val_metrics['positive_rate_actual']:.2%})
- **Held-Out Test:** {len(test_df):,} rows (actual positive rate: {test_metrics['positive_rate_actual']:.2%})

## Measured Performance Metrics

| Metric | Validation Set | Held-Out Test Set |
|---|---|---|
| **ROC-AUC** | {val_metrics['roc_auc']:.4f} | {test_metrics['roc_auc']:.4f} |
| **PR-AUC (Average Precision)** | {val_metrics['average_precision']:.4f} | {test_metrics['average_precision']:.4f} |
| **Brier Score (MSE to label)** | {val_metrics['brier_score']:.4f} | {test_metrics['brier_score']:.4f} |
| **ECE (10-bin Calibration Error)** | {val_metrics['ece_10bin']:.4f} | {test_metrics['ece_10bin']:.4f} |
| **Accuracy (@ 0.50)** | {val_metrics['accuracy']:.4f} | {test_metrics['accuracy']:.4f} |
| **Precision (@ 0.50)** | {val_metrics['precision']:.4f} | {test_metrics['precision']:.4f} |
| **Recall (@ 0.50)** | {val_metrics['recall']:.4f} | {test_metrics['recall']:.4f} |
| **F1-Score (@ 0.50)** | {val_metrics['f1']:.4f} | {test_metrics['f1']:.4f} |

## Top Predictive Features (LightGBM Split Importance)
| Feature | Importance |
|---|---|
"""
        + "\n".join(f"| {f['feature']} | {f['importance']} |" for f in top_features)
        + """

## Methodological Safeguards
1. **No Data Leakage:** Preprocessor fitted strictly on training partition only.
2. **Held-out Test Evaluation:** Evaluated once only on the untouched test partition.
3. **Deterministic Fallback:** If model artifact is absent or fails to load, `MLScoringService` falls back to the deterministic heuristic.
4. **Safety Invariant:** Model predictions inform reasoning and ranking; the deterministic Policy Engine authorizes actions, and the Recovery Verifier authoritatively confirms outcomes.
"""
    )
    (output_dir / "evaluation_report.md").write_text(report_md, encoding="utf-8")
    print(f"All artifacts and reports written to {output_dir}")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data" / "training"
    output_dir = base_dir / "models" / "artifacts"
    train_and_evaluate(data_dir=data_dir, output_dir=output_dir)
