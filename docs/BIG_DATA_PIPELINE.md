# Big Data Pipeline & Distributed Analytics — RevenueRescue AI

## 1. Architectural Overview

Financial recovery operations process millions of events across payment gateways, subscription billings, and checkout interactions. Single-node processing libraries (e.g. Pandas) fail at enterprise scale due to memory limits (`OOM`).

RevenueRescue AI implements an end-to-end **Apache Spark (PySpark 4.2.0)** pipeline designed for:
1. Distributed, schema-enforced event ingestion.
2. Leakage-free point-in-time window transformations.
3. Columnar Snappy-compressed Parquet storage with partition pruning.
4. Distributed Spark SQL analytical queries with optimized physical execution plans.

---

## 2. Ingestion & Schema Enforcement

The raw dataset (`data/training/payment_events.csv`, 100,000 rows, 14.2 MB) is ingested using an explicit `StructType` schema. This prevents expensive runtime schema inference and enforces strict type constraints at the ingestion boundary:

```python
RAW_EVENT_SPARK_SCHEMA = StructType(
    [
        StructField("schema_version", StringType(), False),
        StructField("event_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("customer_id", StringType(), False),
        StructField("amount_paise", LongType(), False),
        StructField("currency", StringType(), False),
        StructField("failure_reason", StringType(), False),
        StructField("occurred_at", StringType(), False),
        StructField("payment_method", StringType(), True),
        StructField("device_type", StringType(), True),
        StructField("country", StringType(), True),
        StructField("retry_count", IntegerType(), False),
        StructField("recovered", BooleanType(), False),
        StructField("is_synthetic", BooleanType(), False),
        StructField("split", StringType(), True),
    ]
)
```

---

## 3. Distributed Window Transformations

To prevent temporal data leakage, customer history features are computed strictly over prior events using PySpark `Window` definitions:

- **Unbounded Past to Current Event:**
  `Window.partitionBy("customer_id").orderBy("occurred_at_sec", "event_id").rowsBetween(Window.unboundedPreceding, Window.currentRow)`
- **Strictly Prior Events Frame:**
  `Window.partitionBy("customer_id").orderBy("occurred_at_sec", "event_id").rowsBetween(Window.unboundedPreceding, -1)`

### Derived Features:
- `cust_prior_events`: Cumulative count of prior events per customer.
- `hours_since_prev_event`: Time difference (in hours) between current event and preceding event using `F.lag`.
- `cust_prior_amount_mean`: Running mean transaction amount across prior attempts.
- `cust_prior_retry_total`: Sum of retry counts attempted in prior events.
- `cust_prior_same_failure_reason`: Cumulative occurrences of the specific failure reason for the customer.

---

## 4. Partitioning & Parquet Storage

The transformed dataset is persisted to `data/spark_processed/events_partitioned.parquet` partitioned by `chrono_split`:

```text
events_partitioned.parquet/
├── chrono_split=train/
│   ├── part-00000.snappy.parquet
│   └── ...
├── chrono_split=validation/
│   ├── part-00000.snappy.parquet
│   └── ...
└── chrono_split=test/
    ├── part-00000.snappy.parquet
    └── ...
```

### Partitioning Design Decision:
- **Avoided high-cardinality partitioning:** Partitioning by `customer_id` (63,154 unique customers) would create the classic **small-file problem**, overwhelming the filesystem/HDFS namenode with tens of thousands of tiny files.
- **Partitioned by chronological split (`chrono_split`):** This enables **partition pruning**. When downstream training tasks query `WHERE chrono_split = 'train'`, Spark reads only the relevant partition directory, bypassing 30% of the dataset on disk.

---

## 5. Spark SQL Analytical Queries

The pipeline registers a temporary view `recovery_events` and executes Spark SQL analytical queries to measure recovery economics:

### Query 1: Revenue at Risk vs. Recovered by Event Type
```sql
SELECT
    event_type,
    COUNT(*) as total_events,
    SUM(CASE WHEN recovered THEN 1 ELSE 0 END) as recovered_events,
    ROUND(AVG(CASE WHEN recovered THEN 1.0 ELSE 0.0 END) * 100, 2) as recovery_rate_pct,
    ROUND(SUM(amount_paise) / 100.0, 2) as total_at_risk_inr,
    ROUND(SUM(CASE WHEN recovered THEN amount_paise ELSE 0 END) / 100.0, 2) as recovered_revenue_inr
FROM recovery_events
GROUP BY event_type
ORDER BY total_events DESC;
```

#### Executed Results:
| Event Type | Total Events | Recovered Events | Recovery Rate | Total at Risk (INR) | Recovered Revenue (INR) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FAILED_PAYMENT** | 54,894 | 35,112 | 63.96% | ₹38,62,43,580.88 | ₹26,79,46,939.55 |
| **FAILED_SUBSCRIPTION** | 25,354 | 16,134 | 63.64% | ₹17,96,75,664.97 | ₹12,33,72,664.44 |
| **CHECKOUT_ABANDONED** | 19,752 | 10,745 | 54.40% | ₹13,91,01,051.81 | ₹8,22,39,701.69 |
| **TOTAL** | **100,000** | **61,991** | **61.99%** | **₹70,50,20,297.66** | **₹47,35,59,305.68** |

---

## 6. Catalyst Execution Plan Analysis

Running `explain()` on Query 1 demonstrates key Big Data execution properties:

```text
== Physical Plan ==
AdaptiveSparkPlan isFinalPlan=false
+- Sort [total_events#127L DESC NULLS LAST], true, 0
   +- Exchange rangepartitioning(total_events#127L DESC NULLS LAST, 4)
      +- HashAggregate(keys=[event_type#2], functions=[count(1), sum(CASE WHEN recovered#12 THEN 1 ELSE 0 END), ...])
         +- Exchange hashpartitioning(event_type#2, 4)
            +- HashAggregate(keys=[event_type#2], functions=[partial_count(1), partial_sum(...), ...])
               +- FileScan csv [event_type#2,amount_paise#4L,recovered#12] 
                  ReadSchema: struct<event_type:string,amount_paise:bigint,recovered:boolean>
```

### Key Optimizations Observed:
1. **Column Projection Pruning:**
   Although the raw CSV has 15 columns and the transformed view has 27 columns, Spark's Catalyst optimizer pruned all unreferenced columns, reading only `[event_type, amount_paise, recovered]`.
2. **Two-Phase Hash Aggregation:**
   - Worker partitions first perform `partial_count` and `partial_sum` locally via `HashAggregate`.
   - An `Exchange hashpartitioning` shuffles the intermediate partial sums across partitions.
   - The final `HashAggregate` merges the partials before global sorting.
3. **Adaptive Query Execution (AQE):**
   Spark dynamically adjusts shuffle partition counts and coalesce stages based on runtime statistics.

---

## 7. Comparative Performance Benchmark: Pandas vs. PySpark

We executed a standardized benchmark (`scripts/benchmark_spark_pandas.py`) on identical hardware and data:

**Environment:** Windows 10 | 12 Logical Cores | 15.73 GB RAM | Python 3.11.9  
**Dataset:** `payment_events.csv` (100,000 rows, 14.2 MB)

| Benchmark Metric | Pandas (`v2.2.3`) | PySpark (`v4.2.0`) | Architectural Significance |
| :--- | :--- | :--- | :--- |
| **Cold Execution Time** | **3.41s** | **21.94s** | Spark incurs JVM boot and Py4J IPC handshake overhead. |
| **Warm Execution Time** | **2.05s** | **0.95s** | Spark's compiled Catalyst plan and Tungsten execution outperforms Pandas on warm data. |
| **Row Count & Math Check** | 100,000 | 100,000 | Exact match across all aggregations. |
| **Memory Architecture** | Single-Node RAM (C/Cython) | Distributed RDD / Tungsten Pages | Spark supports out-of-core execution. |

### Engineering Verdict on Scale:
- At small scale (100k rows, 15 MB), single-node Pandas has lower startup latency because contiguous C arrays avoid JVM inter-process communication.
- At Big Data scale (10M to 1B rows, 15 GB to 1.5 TB), Pandas will crash with an out-of-memory error (`OOM`), whereas PySpark partitions the workload horizontally across worker nodes.
