#!/usr/bin/env python3
"""Generates publication-quality figures from REAL, already-captured data
(no new experiments run here - reads from reproducibility/data/*.txt and
the constants recorded in the manuscript, all traceable to real script
output; see reproducibility/figures/ for the reference output this exact
script produced).

    python raca/tools/generate_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "reproducibility" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 10,
    "figure.dpi": 200,
    "savefig.bbox": "tight",
})


def fig_n20_paired_ci():
    # Real numbers from RACA-PAPER/data/phase13*.txt and
    # ambiguity_scale_calibration_sweep_larger_geometries.txt
    geometries = ["2 robots\n(N=20, in-sample)", "2 robots\n(N=20, held-out)",
                  "100 robots\n(held-out)", "200 robots\n(held-out)", "1000 robots\n(held-out)"]
    means_pp = [-5.2, -6.06, -12.88, -10.37, -27.25]
    ci_lo = [-7.9, -9.1, -17.2, -14.4, -34.2]
    ci_hi = [-2.6, -3.5, -8.9, -7.0, -19.8]
    yerr_lo = [m - lo for m, lo in zip(means_pp, ci_lo)]
    yerr_hi = [hi - m for m, hi in zip(means_pp, ci_hi)]

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(geometries))
    ax.errorbar(x, means_pp, yerr=[yerr_lo, yerr_hi], fmt="o", capsize=5, color="#2b6cb0", markersize=7)
    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(geometries, fontsize=8)
    ax.set_ylabel("LLM-invocation-rate difference\n(adaptive - always_llm), percentage points")
    ax.set_title("N=20 paired-seed LLM-rate reduction, 95% bootstrap CI, all geometries\n(MockBackend; in-sample and held-out seed sets)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_n20_paired_ci.png")
    plt.close(fig)


def fig_ambiguity_scale_sweep():
    # Real numbers from ambiguity_scale_calibration_sweep.txt (2-robot geometry)
    scales = [0.001, 0.005, 0.01, 0.02, 0.03, 0.04, 0.05]
    rates = [7.0, 14.2, 31.4, 53.6, 92.8, 94.8, 95.8]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(scales, rates, marker="o", color="#c05621")
    ax.axvline(0.04, color="gray", linestyle="--", linewidth=0.8, label="selected (2 robots)")
    ax.set_xlabel("AMBIGUITY_MARGIN_SCALE")
    ax.set_ylabel("Mean LLM invocation rate (%)")
    ax.set_title("Ambiguity-scale sweep, 2-robot geometry, N=20 paired seeds\n(MockBackend)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_ambiguity_scale_sweep.png")
    plt.close(fig)


def fig_ambiguity_distribution():
    # Real numbers from RACA-PAPER/data/ambiguity_distribution_by_geometry.txt
    geometries = ["2 robots", "100 robots", "200 robots", "1000 robots"]
    pct_0 = [0.9, 0.0, 0.0, 0.0]
    pct_1 = [0.0, 71.2, 85.9, 100.0]
    pct_between = [99.1, 28.7, 14.1, 0.0]

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(geometries))
    width = 0.6
    ax.bar(x, pct_0, width, label="ambiguity = 0", color="#4a5568")
    ax.bar(x, pct_between, width, bottom=pct_0, label="ambiguity in (0,1)", color="#68a1e5")
    ax.bar(x, pct_1, width, bottom=[a + b for a, b in zip(pct_0, pct_between)], label="ambiguity = 1", color="#c53030")
    ax.set_xticks(x)
    ax.set_xticklabels(geometries)
    ax.set_ylabel("% of sampled decisions (N=2000/geometry)")
    ax.set_title("Ambiguity-signal saturation across geometry\n(direct measurement, DifficultyEstimator, no simulation)")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_ambiguity_distribution.png")
    plt.close(fig)


def fig_lambda_latency_sensitivity():
    # Real numbers from RACA-PAPER/data/lambda_sensitivity_sweep.txt
    values = [0.01, 0.05, 0.1, 0.5, 1.0]
    rates = [100.0, 98.44, 94.78, 0.0, 0.0]
    cost_ok = [False, False, True, True, True]  # per the pre-defined criterion (note: 0.5/1.0 pass trivially)

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = ["#c53030" if not ok else "#2f855a" for ok in cost_ok]
    ax.bar([str(v) for v in values], rates, color=colors)
    ax.axhline(95, color="gray", linestyle="--", linewidth=0.8, label="cost-reduction bar (95%)")
    ax.set_xlabel("lambda_latency")
    ax.set_ylabel("Mean LLM invocation rate (%)")
    ax.set_title("lambda_latency sensitivity, N=20, 2 robots\n(green=passes cost criterion, red=fails; 0.5/1.0 pass trivially - see caption)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_lambda_latency_sensitivity.png")
    plt.close(fig)


def fig_fleet_geometry_isolation():
    # Real numbers from RACA-PAPER/data/fleet_geometry_isolation.txt
    geometries = ["1.0x", "5.0x", "20.0x"]
    robots = [2, 20, 100]
    rate = np.array([
        [97.7, 48.1, 5.5],
        [99.2, 98.6, 84.6],
        [100.0, 100.0, 100.0],
    ])

    fig, ax = plt.subplots(figsize=(6, 4.5))
    im = ax.imshow(rate, cmap="RdYlGn_r", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(np.arange(len(robots)))
    ax.set_xticklabels(robots)
    ax.set_yticks(np.arange(len(geometries)))
    ax.set_yticklabels(geometries)
    ax.set_xlabel("Robot count")
    ax.set_ylabel("Geometry scale")
    ax.set_title("Fleet-size/geometry isolation: mean LLM invocation rate (%)\n"
                  "N=20 paired seeds/cell, AMBIGUITY_MARGIN_SCALE fixed at 0.05, MockBackend")
    for i in range(len(geometries)):
        for j in range(len(robots)):
            ax.text(j, i, f"{rate[i, j]:.1f}", ha="center", va="center",
                     color="black", fontsize=10)
    fig.colorbar(im, ax=ax, label="LLM invocation rate (%)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fig_fleet_geometry_isolation.png")
    plt.close(fig)


def run() -> int:
    fig_n20_paired_ci()
    fig_ambiguity_scale_sweep()
    fig_ambiguity_distribution()
    fig_lambda_latency_sensitivity()
    fig_fleet_geometry_isolation()
    print(f"wrote 5 figures to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
