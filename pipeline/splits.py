"""
Canonical chronological split rule shared by the Pandas and Spark pipelines.

Rule ``rr-split.v2``
--------------------
Sort all events by ``occurred_at``. For a fraction ``q`` let ``k = floor(q * N)`` and let the
cut-off ``c_q`` be the ``k``-th smallest timestamp (0-based). An event is in

* ``train``       if ``occurred_at <  c_0.70``
* ``validation``  if ``c_0.70 <= occurred_at < c_0.85``
* ``test``        otherwise.

Events with equal timestamps always fall in the same split, so no split boundary separates two
events that happened at the same instant. The rule is exact (no interpolation, no approximate
quantiles) and can be computed in Spark with a grouped cumulative count.

Ordering inside a customer's history uses ``(occurred_at, event_id)``; ``event_id`` is the
deterministic tie-breaker for events with the same timestamp.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SPLIT_RULE_VERSION = "rr-split.v2"
SPLIT_FRACTIONS = (0.70, 0.85)
SPLIT_NAMES = ("train", "validation", "test")
SEQUENCE_ORDER = ["customer_id", "occurred_at", "event_id"]
SPLIT_RULE_TEXT = (
    "rr-split.v2: cut-off c_q = k-th smallest occurred_at with k = floor(q*N), q in (0.70, 0.85); "
    "train if t < c_0.70, validation if c_0.70 <= t < c_0.85, else test. Equal timestamps share a split."
)


def chrono_cutoffs(timestamps: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Exact cut-offs for :data:`SPLIT_FRACTIONS`."""
    ts = pd.Series(timestamps).dropna().sort_values(kind="mergesort").reset_index(drop=True)
    if ts.empty:
        raise ValueError("cannot compute split cut-offs from an empty timestamp column")
    n = len(ts)
    return tuple(ts.iloc[min(int(np.floor(q * n)), n - 1)] for q in SPLIT_FRACTIONS)  # type: ignore[return-value]


def assign_chrono_split(timestamps: pd.Series, cutoffs: tuple) -> np.ndarray:
    t70, t85 = cutoffs
    return np.select(
        [timestamps < t70, timestamps < t85], ["train", "validation"], default="test"
    ).astype(object)
