#!/usr/bin/env python3
"""Turn the Task 1 ChampSim outputs into tables and bar plots.

Usage (from the repo root):  python3 scripts/parse_task1.py

Reads results/<config>/<trace>.txt for baseline (no prefetcher), ip_stride and spp, all with LRU at the
L2C, and writes results/task1_results.csv, results/task1_results.md and results/plots/task1_*.png.
Speedup is IPC divided by the baseline IPC. Prefetch accuracy is ChampSim's L1D accuracy, and coverage is
(baseline L1D load misses - L1D load misses) / baseline L1D load misses, as defined in the PDF.
"""
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = "results"
OUT = os.path.join(RES, "plots")
os.makedirs(OUT, exist_ok=True)
TRACES = ["Trace1", "Trace2", "Trace3"]
CONFIGS = ["baseline", "ip_stride", "spp"]
LABEL = {"baseline": "No prefetcher", "ip_stride": "IP-stride", "spp": "SPP"}

PATTERNS = {
    "IPC":           r"^CPU 0 cumulative IPC:\s*([\d.]+)",
    "L1D_LOAD_MISS": r"^L1D LOAD\s+ACCESS:\s*\d+\s+HIT:\s*\d+\s+MISS:\s*(\d+)",
    "L1D_LOAD_MPKI": r"^L1D LOAD\s+ACCESS:.*MPKI:\s*([\d.]+)",
    "PF_ACCURACY":   r"^L1D USEFUL LOAD PREFETCHES:.*ACCURACY:\s*([\d.]+)",
}


def parse(path):
    text = open(path, errors="ignore").read()
    if "ChampSim completed all CPUs" not in text:
        raise SystemExit(f"{path} did not finish")
    vals = {}
    for k, p in PATTERNS.items():
        m = re.findall(p, text, re.M)
        vals[k] = float(m[-1]) if m else float("nan")
    return vals


df = pd.DataFrame([dict(config=c, trace=t, **parse(f"{RES}/{c}/{t}.txt"))
                   for t in TRACES for c in CONFIGS])
base = df[df.config == "baseline"].set_index("trace")
df["Speedup"] = df.IPC / df.trace.map(base.IPC)
df["Coverage"] = 100.0 * (df.trace.map(base.L1D_LOAD_MISS) - df.L1D_LOAD_MISS) / df.trace.map(base.L1D_LOAD_MISS)
df.loc[df.config == "baseline", ["PF_ACCURACY", "Coverage"]] = float("nan")   # no prefetcher, nothing to measure
df = df.drop(columns="L1D_LOAD_MISS")

summary = pd.DataFrame([{"config": c, "geomean_speedup": float(np.exp(np.log(s.Speedup).mean()))}
                        for c in CONFIGS for s in [df[df.config == c]]])


def write_md(fh, table):
    cols = list(table.columns)
    fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
    for _, r in table.iterrows():
        fh.write("| " + " | ".join(f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c])
                                    for c in cols) + " |\n")


df.to_csv(os.path.join(RES, "task1_results.csv"), index=False)
with open(os.path.join(RES, "task1_results.md"), "w") as fh:
    write_md(fh, df)
    fh.write("\n")
    write_md(fh, summary)
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print()
print(summary.to_string(index=False, float_format=lambda x: f"{x:.5f}"))


def bar_plot(metric, configs, fname, ylabel, title, baseline_line=False):
    piv = df[df.config.isin(configs)].pivot(index="trace", columns="config", values=metric)[configs]
    piv.columns = [LABEL[c] for c in piv.columns]
    ax = piv.plot(kind="bar", figsize=(8, 5), edgecolor="grey", rot=0)
    if baseline_line:
        ax.axhline(1.0, color="red", ls="--", lw=1, label="Baseline")
        lo, hi = piv.min().min(), piv.max().max()
        ax.set_ylim(min(lo, 1.0) - 0.005, max(hi, 1.0) + 0.005)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Traces")
    ax.set_title(title)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, fname), dpi=150)
    plt.close()


bar_plot("Speedup", CONFIGS, "task1_speedup.png", "Speedup over no prefetcher",
         "Task 1: speedup", baseline_line=True)
bar_plot("IPC", CONFIGS, "task1_IPC.png", "IPC", "Task 1: IPC")
bar_plot("L1D_LOAD_MPKI", CONFIGS, "task1_L1D_LOAD_MPKI.png", "L1D Load MPKI", "Task 1: L1D load MPKI")
bar_plot("PF_ACCURACY", ["ip_stride", "spp"], "task1_accuracy.png", "L1D prefetch accuracy (%)",
         "Task 1: prefetch accuracy")
bar_plot("Coverage", ["ip_stride", "spp"], "task1_coverage.png", "L1D coverage (%)", "Task 1: prefetch coverage")

print(f"\nTables: {RES}/task1_results.csv, {RES}/task1_results.md\nPlots:  {OUT}/task1_*.png")
