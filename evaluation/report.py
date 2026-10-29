"""
Canonical evaluation report writer.

Layout::

    reports/evaluation/
        runs/<run_id>/            every run, complete or not
            report.json, report.md, *.csv, figures/*.png
        latest.json, latest.md, *.csv, figures/   copy of the most recent *complete* run

A run is promoted to ``latest`` only when ``report["status"] == "complete"``. Promotion writes
into a staging directory first and then replaces files, so a crash cannot leave a half-written
``latest``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from evaluation.metrics import METRIC_INFO, dumps

TRACKED_PACKAGES = (
    "numpy", "pandas", "scikit-learn", "lightgbm", "torch", "pyarrow", "pyspark", "matplotlib",
)


class ReportPromotionError(RuntimeError):
    """Raised when an incomplete report would replace the canonical one."""


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def environment_info() -> dict[str, Any]:
    versions = {}
    for pkg in TRACKED_PACKAGES:
        try:
            versions[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            versions[pkg] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "packages": versions,
    }


def new_run_id(prefix: str = "eval") -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def render_markdown(report: Mapping[str, Any]) -> str:
    """Human-readable summary generated only from values in ``report``."""
    ds, prot = report["dataset"], report["protocol"]
    lines = [
        "# RevenueRescue AI — Canonical Model Evaluation",
        "",
        f"- **Run ID:** `{report['run_id']}`  (status: {report['status']})",
        f"- **Generated (UTC):** {report['generated_at_utc']}",
        f"- **Dataset:** `{ds['path']}` sha256 `{ds['sha256'][:16]}…`, {ds['rows']:,} rows, "
        f"feature version `{ds['feature_version']}`, synthetic: {ds['synthetic']}",
        f"- **Split:** `{ds['split_column']}` — {ds['split_rule']}",
        f"- **Seed:** {report['seed']}",
        f"- **Threshold rule:** {prot['threshold_selection']}",
        f"- **Calibration rule:** {prot['calibration_selection']}",
        f"- **Test-set use:** {prot['test_usage']}",
        "",
        "All numbers are on a **synthetic** label. They describe predictive quality, not recovered revenue.",
        "",
        "## Splits",
        "",
        "| Split | Rows | Positives | Prevalence | Start (UTC) | End (UTC) |",
        "|---|---:|---:|---:|---|---|",
    ]
    for s in ds["splits"]:
        lines.append(
            f"| {s['split']} | {s['rows']:,} | {s['positives']:,} | {_fmt(s['prevalence'])} | "
            f"{s['start']} | {s['end']} |"
        )

    def table(title: str, keys: list[str], split: str, note: str) -> None:
        lines.extend(["", f"## {title}", "", note, ""])
        lines.append("| Model | " + " | ".join(keys) + " |")
        lines.append("|---|" + "---:|" * len(keys))
        for name, m in report["models"].items():
            vals = {**m[split]["metrics"], "threshold": m[split].get("threshold")}
            cells = [_fmt(vals.get(k), 2 if k == "threshold" else 4) for k in keys]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")

    table("Ranking metrics (test)", ["roc_auc", "pr_auc"], "test",
          "Threshold-free; computed from probabilities. PR-AUC baseline = test prevalence.")
    table("Probability quality (test)", ["log_loss", "brier", "ece", "mce"], "test",
          "Computed from probabilities. Lower is better.")
    table("Probability-error metrics on the 0/1 target (test)",
          ["mse", "rmse", "mae", "medae", "mean_error", "r2", "nrmse_range", "mape_nonzero_pct"],
          "test",
          "Regression-style errors between probability and label. MSE equals Brier; R² is the "
          "Brier skill score against the test prevalence; NRMSE uses the target range (=1 here); "
          "MAPE excludes y=0 rows and is not a primary metric.")
    table("Classification at each model's validation-selected threshold (test)",
          ["threshold", "accuracy", "precision", "recall", "specificity", "f1", "balanced_accuracy",
           "mcc", "cohen_kappa", "npv", "fpr", "fnr", "coverage"],
          "test",
          "Each row is one operating point (one confusion matrix) chosen on validation.")

    lines.extend(["", "## Confusion matrices (test)", "", "| Model | TN | FP | FN | TP |", "|---|---:|---:|---:|---:|"])
    for name, m in report["models"].items():
        cm = m["test"]["confusion_matrix"]
        lines.append(f"| {name} | {cm['tn']:,} | {cm['fp']:,} | {cm['fn']:,} | {cm['tp']:,} |")

    lines.extend(["", "## 95% bootstrap confidence intervals (test)", "",
                  f"{report['bootstrap']['method']}.", "",
                  "| Model | Metric | Point | Low | High |", "|---|---|---:|---:|---:|"])
    for name, m in report["models"].items():
        for metric, ci in m.get("test_ci", {}).items():
            lines.append(f"| {name} | {metric} | {_fmt(ci['point'])} | {_fmt(ci['low'])} | {_fmt(ci['high'])} |")

    if report.get("comparisons"):
        lines.extend(["", "## Paired comparisons (test, same resamples)", "",
                      "| Comparison | Metric | Difference | 95% CI |", "|---|---|---:|---|"])
        for c in report["comparisons"]:
            lines.append(f"| {c['a']} − {c['b']} | {c['metric']} | {_fmt(c['difference'])} | "
                         f"[{_fmt(c['low'])}, {_fmt(c['high'])}] |")
        lines.extend(["", "A CI containing 0 means the difference is not distinguishable from "
                      "resampling noise on this test set; it does not prove the models are equivalent."])

    if report.get("operating_points"):
        lines.extend(["", "## Operating points of the recommended model", "",
                      "Thresholds chosen on validation, then applied unchanged to test.", "",
                      "| Policy | Threshold | Feasible on val | Test precision | Test recall | Test coverage | Test FP | Test FN |",
                      "|---|---:|---|---:|---:|---:|---:|---:|"])
        for op in report["operating_points"]:
            t = op["test"]
            lines.append(f"| {op['policy']} | {op['threshold']:.2f} | {op['feasible']} | {_fmt(t['precision'])} | "
                         f"{_fmt(t['recall'])} | {_fmt(t['coverage'])} | {t['fp']:,} | {t['fn']:,} |")

    if report.get("undefined_metrics"):
        lines.extend(["", "## Undefined metrics", ""])
        for k, v in report["undefined_metrics"].items():
            lines.append(f"- {k}: {v}")

    rec = report.get("recommendation", {})
    if rec:
        lines.extend(["", "## Recommendation", "", f"**{rec['model']}** — {rec['reason']}"])
    if report.get("limitations"):
        lines.extend(["", "## Limitations", ""] + [f"- {x}" for x in report["limitations"]])

    lines.extend(["", "## Metric glossary", "", "| Metric | Full name | Family | Formula |", "|---|---|---|---|"])
    for k, info in METRIC_INFO.items():
        lines.append(f"| `{k}` | {info.full_name} | {info.family} | `{info.formula}` |")
    env = report["environment"]
    lines.extend(["", "## Environment", "", f"Python {env['python']} on {env['platform']}, {env['cpu_count']} logical CPUs.", ""])
    lines.append(", ".join(f"{k} {v}" for k, v in env["packages"].items() if v))
    return "\n".join(lines) + "\n"


def write_run(
    report: Mapping[str, Any],
    out_root: Path,
    tables: Mapping[str, Any] | None = None,
    figures_dir: Path | None = None,
) -> Path:
    """Write a run directory. ``tables`` maps file name → pandas DataFrame."""
    run_dir = out_root / "runs" / str(report["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(dumps(report, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    for name, df in (tables or {}).items():
        df.to_csv(run_dir / name, index=False)
    if figures_dir is not None and figures_dir.exists() and figures_dir != run_dir / "figures":
        shutil.copytree(figures_dir, run_dir / "figures", dirs_exist_ok=True)
    return run_dir


def promote_to_latest(run_dir: Path, out_root: Path, report: Mapping[str, Any]) -> None:
    """Copy a complete run to ``latest.*``. Refuses incomplete runs."""
    if report.get("status") != "complete":
        raise ReportPromotionError(
            f"run {report.get('run_id')} has status {report.get('status')!r}; "
            "the canonical report was left unchanged"
        )
    staging = out_root / ".staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copy2(run_dir / "report.json", staging / "latest.json")
    shutil.copy2(run_dir / "report.md", staging / "latest.md")
    for csv in run_dir.glob("*.csv"):
        shutil.copy2(csv, staging / csv.name)
    if (run_dir / "figures").exists():
        shutil.copytree(run_dir / "figures", staging / "figures")
    if (out_root / "figures").exists():
        shutil.rmtree(out_root / "figures")
    for item in staging.iterdir():
        target = out_root / item.name
        if item.is_dir():
            shutil.move(str(item), str(target))
        else:
            os.replace(item, target)
    shutil.rmtree(staging)
