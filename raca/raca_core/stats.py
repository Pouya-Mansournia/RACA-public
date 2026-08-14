"""Bootstrap confidence intervals for RACA's own experiment scripts.

Ported from the prior research line's ``generate_report.py`` (function
``compute_metric_statistics``), which already implemented a percentile
bootstrap and sat unused against Phase 13's N=20 campaign. This is the
same method, just given a home inside raca_core so any script here can
call it without reaching into legacy-phase1.
"""
from __future__ import annotations

import random
import statistics
from typing import List, Optional


def _percentile(values: List[float], p: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = p * (len(ordered) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def compute_metric_statistics(
    values: List[float], *, n_bootstrap: int = 2000, seed: int = 0
) -> Optional[dict]:
    """N, mean, median, stdev, min, max, p95, and a percentile-bootstrap 95% CI on the mean.

    Returns None for an empty list. Uses a seeded local Random instance so
    the same input always gives the same CI.
    """
    if not values:
        return None
    n = len(values)
    result = {
        "n": n,
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "stdev": round(statistics.stdev(values), 4) if n > 1 else None,
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "p95": round(_percentile(values, 0.95), 4),
        "ci95_low": None,
        "ci95_high": None,
    }
    if n > 1:
        rng = random.Random(seed)
        boot_means = sorted(
            statistics.mean(values[rng.randrange(n)] for _ in range(n))
            for _ in range(n_bootstrap)
        )
        lo_idx = int(0.025 * n_bootstrap)
        hi_idx = max(int(0.975 * n_bootstrap) - 1, 0)
        result["ci95_low"] = round(boot_means[lo_idx], 4)
        result["ci95_high"] = round(boot_means[hi_idx], 4)
    return result
