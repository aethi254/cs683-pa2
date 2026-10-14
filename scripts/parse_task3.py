#!/usr/bin/env python3
"""Turn the Task 3 ChampSim outputs into tables and bar plots.

Usage (from the repo root):  python3 scripts/parse_task3.py

Reads the Task 3 runs in results_task3/ and the reference runs from earlier tasks:
  baseline   results/baseline/<trace>.txt          no prefetcher, LRU L2C
  spp        results/spp/<trace>.txt               SPP, LRU L2C (Task 1B)
  dyn        results_task2/dyn_t0.25_<trace>.txt   no prefetcher, dynamic I-RRIP (Task 2B)
and writes results_task3/task3_results.csv, task3_results.md and results_task3/plots/task3_*.png.
Speedup is IPC divided by the baseline IPC, and coverage is
(baseline L1D load misses - L1D load misses) / baseline L1D load misses, as defined in the PDF.
"""
import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = "results_task3"
OUT = os.path.join(RES, "plots")
os.makedirs(OUT, exist_ok=True)
TRACES = ["Trace1", "Trace2", "Trace3"]
FINAL = "spp_pfdyn_t0.55"

PATTERNS = {
    "IPC":            r"^CPU 0 cumulative IPC:\s*([\d.]+)",
    "L1D_LOAD_MISS":  r"^L1D LOAD\s+ACCESS:\s*\d+\s+HIT:\s*\d+\s+MISS:\s*(\d+)",
    "L1D_LOAD_MPKI":  r"^L1D LOAD\s+ACCESS:.*MPKI:\s*([\d.]+)",
    "PF_ACCURACY":    r"^L1D USEFUL LOAD PREFETCHES:.*ACCURACY:\s*([\d.]+)",
    "L2C_LOAD_MPKI":  r"^L2C LOAD\s+ACCESS:.*MPKI:\s*([\d.]+)",
    "L2C_INSTR_MPKI": r"^L2C INSTRUCTION LOAD MPKI:\s*([\d.]+)",
    "L2C_DATA_MPKI":  r"^L2C DATA LOAD MPKI:\s*([\d.]+)",
}

LABEL = {"baseline": "No prefetcher, LRU", "spp": "SPP, LRU",
         "dyn": "No prefetcher, Dyn I-RRIP", "spp_dyn": "SPP + Dyn I-RRIP",
         FINAL: "SPP + prefetch-aware Dyn I-RRIP"}


def label(c):
    return LABEL.get(c, "SPP + PF-aware Dyn I-RRIP (thr " + c[11:] + ")")


def parse(path):
    text = open(path, errors="ignore").read()
    if "ChampSim completed all CPUs" not in text:
        raise SystemExit(f"{path} did not finish")
    vals = {}
    for k, p in PATTERNS.items():
        m = re.findall(p, text, re.M)
        vals[k] = float(m[-1]) if m else float("nan")
    return vals


files = {}
for t in TRACES:
    files[("baseline", t)] = f"results/baseline/{t}.txt"
    files[("spp", t)] = f"results/spp/{t}.txt"
    files[("dyn", t)] = f"results_task2/dyn_t0.25_{t}.txt"
for f in glob.glob(os.path.join(RES, "*_Trace*.txt")):
    cfg, t = os.path.basename(f)[:-4].rsplit("_", 1)
    files[(cfg, t)] = f

rows = [dict(config=c, trace=t, **parse(f)) for (c, t), f in files.items()]
df = pd.DataFrame(rows)
base = df[df.config == "baseline"].set_index("trace")
df["Speedup"] = df.IPC / df.trace.map(base.IPC)
df["Coverage"] = 100.0 * (df.trace.map(base.L1D_LOAD_MISS) - df.L1D_LOAD_MISS) / df.trace.map(base.L1D_LOAD_MISS)
no_pf = df.config.isin(["baseline", "dyn"])
df.loc[no_pf, ["PF_ACCURACY", "Coverage"]] = float("nan")   # no prefetcher, nothing to measure

order = ["baseline", "spp", "dyn", "spp_dyn"] + sorted(c for c in df.config.unique() if c.startswith("spp_pfdyn"))
df["_rank"] = df.config.map(order.index)
df = df.sort_values(["trace", "_rank"]).drop(columns=["_rank", "L1D_LOAD_MISS"])

summary = pd.DataFrame([{"config": c, "geomean_speedup": float(np.exp(np.log(s.Speedup).mean()))}
                        for c in order for s in [df[df.config == c]]])


def write_md(fh, table):
    cols = list(table.columns)
    fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
    for _, r in table.iterrows():
        fh.write("| " + " | ".join(f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c])
                                    for c in cols) + " |\n")


df.to_csv(os.path.join(RES, "task3_results.csv"), index=False)
with open(os.path.join(RES, "task3_results.md"), "w") as fh:
    write_md(fh, df)
    fh.write("\n")
    write_md(fh, summary)
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print()
print(summary.to_string(index=False, float_format=lambda x: f"{x:.5f}"))


def bar_plot(metric, configs, fname, ylabel, title, baseline_line=False):
    sub = df[df.config.isin(configs)]
    piv = sub.pivot(index="trace", columns="config", values=metric)[configs]
    piv.columns = [label(c) for c in piv.columns]
    ax = piv.plot(kind="bar", figsize=(9, 5), edgecolor="grey", rot=0)
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


main = ["baseline", "spp", "dyn", "spp_dyn", FINAL]
with_pf = ["spp", "spp_dyn", FINAL]
bar_plot("Speedup", main, "task3_speedup.png", "Speedup over no prefetcher + LRU",
         "Task 3: speedup", baseline_line=True)
bar_plot("IPC", main, "task3_IPC.png", "IPC", "Task 3: IPC")
for metric, ylabel in [("L1D_LOAD_MPKI", "L1D Load MPKI"), ("L2C_LOAD_MPKI", "L2C Load MPKI"),
                       ("L2C_INSTR_MPKI", "L2 Instruction Load MPKI"),
                       ("L2C_DATA_MPKI", "L2 Data Load MPKI")]:
    bar_plot(metric, main, f"task3_{metric}.png", ylabel, f"Task 3: {ylabel}")
bar_plot("PF_ACCURACY", with_pf, "task3_accuracy.png", "L1D prefetch accuracy (%)",
         "Task 3: prefetch accuracy")
bar_plot("Coverage", with_pf, "task3_coverage.png", "L1D coverage (%)", "Task 3: prefetch coverage")
sens = [c for c in order if c.startswith("spp_pfdyn")]
bar_plot("Speedup", sens, "task3_sensitivity_speedup.png", "Speedup over no prefetcher + LRU",
         "Task 3: threshold sensitivity (prefetch-aware mode)", baseline_line=True)

print(f"\nTables: {RES}/task3_results.csv, {RES}/task3_results.md\nPlots:  {OUT}/task3_*.png")
