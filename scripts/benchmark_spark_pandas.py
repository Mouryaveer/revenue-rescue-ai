"""
Pandas vs PySpark benchmark for the RevenueRescue AI preprocessing pipeline.

What is measured (wall clock, ``time.perf_counter``):

* Pandas: CSV read, feature transformation, aggregation — cold (first call in the process) and
  warm (repeat on the in-memory frame), each repeated ``--repeats`` times for warm.
* Spark (local mode, one JVM on this machine): session start-up (cold JVM), CSV read + transform +
  aggregation action (cold = first job in a new session, warm = same session again, uncached).
* Correctness: every engineered feature and the split label compared row by row (joined on
  ``event_id``), plus aggregate reconciliation, with documented tolerances.
* Execution plan: partition and column pruning are read from the physical plan of a query over the
  written Parquet, not asserted.

Memory: the Pandas figure is the increase in this process's RSS (psutil) and is approximate. The
Spark JVM runs in a separate process; its memory is not measured here.

Outputs ``reports/benchmarks/benchmark_spark_pandas.{json,md}``.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psutil

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from pipeline.pandas_preprocessor import PandasPreprocessor
from pipeline.spark_pipeline import FEATURE_COLUMNS, SparkBigDataPipeline

FLOAT_TOL = 1e-9
CATEGORICAL = {"event_type", "failure_reason", "payment_method", "device_type", "country"}


def _timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def pandas_agg(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby("event_type").agg(
        total_events=("event_id", "size"),
        recovered_events=("recovered", "sum"),
        recovery_rate=("recovered", "mean"),
        total_at_risk_paise=("amount_paise", "sum"),
    )


SPARK_AGG_SQL = """
    SELECT event_type, COUNT(*) AS total_events,
           SUM(CAST(recovered AS INT)) AS recovered_events,
           AVG(CAST(recovered AS DOUBLE)) AS recovery_rate,
           SUM(amount_paise) AS total_at_risk_paise
    FROM bench_events GROUP BY event_type
"""


def compare_features(p: pd.DataFrame, s: pd.DataFrame) -> dict[str, Any]:
    p = p.set_index("event_id").sort_index()
    s = s.set_index("event_id").sort_index()
    out: dict[str, Any] = {"ids_identical": bool(p.index.equals(s.index)), "columns": {}}
    if not out["ids_identical"]:
        return out
    for col in [*FEATURE_COLUMNS, "chrono_split"]:
        if col in CATEGORICAL or col == "chrono_split":
            mism = int((p[col].astype(str) != s[col].astype(str)).sum())
            out["columns"][col] = {"mismatches": mism, "max_abs_diff": None}
            continue
        a, b = p[col].astype(float).to_numpy(), s[col].astype(float).to_numpy()
        nan_mism = int((np.isnan(a) != np.isnan(b)).sum())
        m = ~np.isnan(a) & ~np.isnan(b)
        diff = np.abs(a[m] - b[m])
        out["columns"][col] = {
            "mismatches": nan_mism + int((diff > FLOAT_TOL).sum()),
            "max_abs_diff": float(diff.max()) if diff.size else 0.0,
        }
    out["all_features_match"] = all(c["mismatches"] == 0 for c in out["columns"].values())
    return out


def compare_aggs(pa: pd.DataFrame, sa: pd.DataFrame) -> dict[str, Any]:
    sa = sa.set_index("event_type").sort_index()
    pa = pa.sort_index()
    res = {"event_types_identical": list(pa.index) == list(sa.index), "columns": {}}
    if res["event_types_identical"]:
        for col in pa.columns:
            d = float(np.max(np.abs(pa[col].astype(float).to_numpy() - sa[col].astype(float).to_numpy())))
            res["columns"][col] = {"max_abs_diff": d, "match": d <= FLOAT_TOL}
    res["all_match"] = res["event_types_identical"] and all(c["match"] for c in res["columns"].values())
    return res


def run_benchmark(csv_path: Path, repeats: int = 3, out_dir: Path | None = None) -> dict[str, Any]:
    out_dir = out_dir or (_ROOT / "reports" / "benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing dataset at {csv_path}")

    proc = psutil.Process()
    vm = psutil.virtual_memory()
    freq = psutil.cpu_freq()
    system = {
        "os": f"{platform.system()} {platform.release()}",
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "cpu_logical": psutil.cpu_count(logical=True),
        "cpu_physical": psutil.cpu_count(logical=False),
        "cpu_max_mhz": round(freq.max, 0) if freq else None,
        "ram_total_gb": round(vm.total / 1024**3, 2),
        "ram_available_gb_at_start": round(vm.available / 1024**3, 2),
    }

    # ── Pandas ───────────────────────────────────────────────────────────
    prep = PandasPreprocessor(data_dir=csv_path.parent, output_dir=Path(tempfile.mkdtemp()))
    rss0 = proc.memory_info().rss
    raw, t_read = _timed(lambda: pd.read_csv(csv_path, low_memory=False))
    (pdf, _, _), t_tf_cold = _timed(lambda: prep.transform(raw))
    pagg, t_agg_cold = _timed(lambda: pandas_agg(pdf))
    rss1 = proc.memory_info().rss
    warm_tf, warm_agg = [], []
    for _ in range(repeats):
        _, t = _timed(lambda: prep.transform(raw))
        warm_tf.append(t)
        _, t = _timed(lambda: pandas_agg(pdf))
        warm_agg.append(t)
    pandas_res = {
        "version": pd.__version__,
        "input_rows": len(raw),
        "output_rows": len(pdf),
        "cold": {"read_csv_sec": t_read, "transform_sec": t_tf_cold, "aggregate_sec": t_agg_cold,
                 "total_sec": t_read + t_tf_cold + t_agg_cold},
        "warm_median": {"transform_sec": statistics.median(warm_tf),
                        "aggregate_sec": statistics.median(warm_agg)},
        "warm_runs": repeats,
        "approx_rss_increase_mb": round((rss1 - rss0) / 1024**2, 1),
    }

    # ── Spark ────────────────────────────────────────────────────────────
    spark_out = Path(tempfile.mkdtemp()) / "spark"
    t0 = time.perf_counter()
    pipe = SparkBigDataPipeline(data_dir=csv_path.parent, output_dir=spark_out)
    t_session = time.perf_counter() - t0
    try:
        spark = pipe.spark

        def spark_job() -> tuple[Any, float, float]:
            ta = time.perf_counter()
            raw_s = pipe.load_raw_events(csv_path.name)
            tf, _ = pipe.transform(raw_s)  # includes the cut-off job
            t_tf = time.perf_counter() - ta
            tf.createOrReplaceTempView("bench_events")
            tb = time.perf_counter()
            rows = spark.sql(SPARK_AGG_SQL).toPandas()
            return (tf, rows), t_tf, time.perf_counter() - tb

        (sdf, sagg), s_tf_cold, s_agg_cold = spark_job()
        s_warm_tf, s_warm_agg = [], []
        for _ in range(repeats):
            _, a, b = spark_job()
            s_warm_tf.append(a)
            s_warm_agg.append(b)
        spark_rows, t_collect = _timed(lambda: sdf.toPandas())
        validation = pipe.validate(pipe.load_raw_events(csv_path.name))
        parquet, t_write = _timed(lambda: pipe.write_partitioned_parquet(sdf))
        pruning = pipe.inspect_pruning(parquet)
        spark_res = {
            "version": spark.version,
            "master": spark.sparkContext.master,
            "default_parallelism": spark.sparkContext.defaultParallelism,
            "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
            "session_time_zone": spark.conf.get("spark.sql.session.timeZone"),
            "input_rows": validation["rows"],
            "output_rows": len(spark_rows),
            "cold": {"session_start_sec": t_session, "read_transform_sec": s_tf_cold,
                     "aggregate_sec": s_agg_cold,
                     "total_sec": t_session + s_tf_cold + s_agg_cold},
            "warm_median": {"read_transform_sec": statistics.median(s_warm_tf),
                            "aggregate_sec": statistics.median(s_warm_agg)},
            "warm_runs": repeats,
            "collect_to_pandas_sec": t_collect,
            "write_partitioned_parquet_sec": t_write,
            "caching": "none (DataFrames are not cached; warm = same JVM/session, re-read from CSV)",
            "memory": "not measured (separate JVM process)",
        }
    finally:
        pipe.stop()

    feature_parity = compare_features(pdf, spark_rows)
    agg_parity = compare_aggs(pandas_agg(pdf), sagg)
    summary = {
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "dataset": {"file": csv_path.name, "bytes": csv_path.stat().st_size,
                    "size_mb": round(csv_path.stat().st_size / 1024**2, 2), "rows": len(raw)},
        "system": system,
        "execution_mode": "local Spark (single machine, local[*]); not a multi-node cluster",
        "pandas": pandas_res,
        "pyspark": spark_res,
        "correctness": {
            "row_counts_identical": pandas_res["output_rows"] == spark_res["output_rows"] == len(raw),
            "feature_parity": feature_parity,
            "aggregate_parity": agg_parity,
            "float_tolerance_abs": FLOAT_TOL,
        },
        "execution_plan": {k: v for k, v in pruning.items() if k != "physical_plan"},
        "limitations": [
            "Single machine; Spark runs in local mode, so no network shuffle or multi-node scheduling is measured.",
            f"Dataset is {round(csv_path.stat().st_size / 1024**2, 1)} MB; fixed JVM and scheduling costs dominate Spark timings at this size.",
            "Spark JVM memory is not measured; the Pandas memory figure is an RSS delta and approximate.",
            "Warm Spark runs reuse the JVM and OS file cache but do not cache DataFrames.",
            f"Timings are medians of {repeats} warm runs on a machine running other software; expect run-to-run variance.",
        ],
    }
    (out_dir / "benchmark_spark_pandas.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (out_dir / "benchmark_spark_pandas.md").write_text(render_md(summary), encoding="utf-8")
    return summary


def render_md(s: dict[str, Any]) -> str:
    p, k, c = s["pandas"], s["pyspark"], s["correctness"]
    fp = c["feature_parity"]
    lines = [
        "# Pandas vs PySpark benchmark",
        "",
        f"- **Generated (UTC):** {s['timestamp_utc']}",
        f"- **Dataset:** `{s['dataset']['file']}`, {s['dataset']['rows']:,} rows, {s['dataset']['size_mb']} MB",
        f"- **Machine:** {s['system']['os']}, {s['system']['cpu_logical']} logical / {s['system']['cpu_physical']} physical CPUs, {s['system']['ram_total_gb']} GB RAM",
        f"- **Mode:** {s['execution_mode']}; Spark master `{k['master']}`, session time zone {k['session_time_zone']}",
        f"- **Versions:** pandas {p['version']}, PySpark {k['version']}, Python {s['system']['python']}",
        "",
        "## Timings (seconds)",
        "",
        "| Stage | Pandas | Spark (local) |",
        "|---|---:|---:|",
        f"| Engine start-up (cold JVM) | – | {k['cold']['session_start_sec']:.2f} |",
        f"| Read CSV (cold) | {p['cold']['read_csv_sec']:.2f} | included below |",
        f"| Transform (cold) | {p['cold']['transform_sec']:.2f} | {k['cold']['read_transform_sec']:.2f} (read + transform + cut-off job) |",
        f"| Aggregate (cold) | {p['cold']['aggregate_sec']:.3f} | {k['cold']['aggregate_sec']:.2f} |",
        f"| **Cold total** | **{p['cold']['total_sec']:.2f}** | **{k['cold']['total_sec']:.2f}** |",
        f"| Transform (warm, median of {p['warm_runs']}) | {p['warm_median']['transform_sec']:.2f} | {k['warm_median']['read_transform_sec']:.2f} |",
        f"| Aggregate (warm, median) | {p['warm_median']['aggregate_sec']:.3f} | {k['warm_median']['aggregate_sec']:.2f} |",
        f"| Write partitioned Parquet | – | {k['write_partitioned_parquet_sec']:.2f} |",
        "",
        f"Approximate Pandas RSS increase: {p['approx_rss_increase_mb']} MB. Spark memory: {k['memory']}.",
        "",
        "## Correctness",
        "",
        f"- Row counts identical: **{c['row_counts_identical']}** ({p['output_rows']:,} vs {k['output_rows']:,})",
        f"- Event IDs identical: **{fp['ids_identical']}**",
        f"- All {len(fp.get('columns', {}))} compared columns match (|diff| ≤ {c['float_tolerance_abs']}, identical NaN pattern): **{fp.get('all_features_match')}**",
        f"- Aggregates by event type match: **{c['aggregate_parity']['all_match']}**",
        "",
        "| Column | Mismatches | Max abs diff |",
        "|---|---:|---:|",
    ]
    for col, r in fp.get("columns", {}).items():
        md = "–" if r["max_abs_diff"] is None else f"{r['max_abs_diff']:.3g}"
        lines.append(f"| `{col}` | {r['mismatches']} | {md} |")
    ep = s["execution_plan"]
    lines += [
        "",
        "## Execution plan observations",
        "",
        f"Query: `{ep['query']}`",
        "",
        f"- Partition pruning in physical plan: **{ep['partition_pruning_in_plan']}** (PartitionFilters: `{ep['partition_filters']}`)",
        f"- Column pruning in physical plan: **{ep['column_pruning_in_plan']}** (ReadSchema: `{ep['read_schema']}`)",
        "",
        "These show what Spark plans to read. They are not a timing claim: no benchmark here compares pruned against unpruned reads.",
        "",
        "## Interpretation",
        "",
        "At this data size Pandas is faster because Spark pays fixed costs (JVM start-up, Py4J, query planning, task scheduling) that dominate a small job. The Spark pipeline exists to provide a scale-out path with identical feature definitions, which the parity checks above verify. This benchmark does not show that the current dataset needs Spark.",
        "",
        "## Limitations",
        "",
        *[f"- {x}" for x in s["limitations"]],
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--csv", type=Path, default=_ROOT / "data" / "training" / "payment_events.csv")
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()
    result = run_benchmark(args.csv, args.repeats)
    print(json.dumps({"pandas_cold_total_sec": result["pandas"]["cold"]["total_sec"],
                      "spark_cold_total_sec": result["pyspark"]["cold"]["total_sec"],
                      "features_match": result["correctness"]["feature_parity"].get("all_features_match"),
                      "aggregates_match": result["correctness"]["aggregate_parity"]["all_match"]}, indent=2))
