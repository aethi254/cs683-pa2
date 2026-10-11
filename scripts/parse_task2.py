#!/usr/bin/env python3
"""Turn the Task 2 ChampSim outputs into tables and bar plots.

Usage (from the repo root):  python3 scripts/parse_task2.py [results_task2]

Reads results_task2/<config>_<trace>.txt (for example irrip_Trace1.txt or
dyn_t0.25_Trace2.txt) and writes:
  results_task2/task2_results.csv   one row per config and trace
  results_task2/task2_results.md    the same rows, plus a per-config summary
                                    (geometric-mean speedup, summed MPKI)
  results_task2/plots/task2*.png    Task 2A, ablation, 2B and sensitivity plots
Speedup is IPC divided by the IPC of the 'lru' run on the same trace.
The set-dueling runs (duel_w*) are left to plot_duel.py.
"""
import glob
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = sys.argv[1] if len(sys.argv) > 1 else "results_task2"
OUT = os.path.join(RES, "plots")
os.makedirs(OUT, exist_ok=True)

PATTERNS = {
    "IPC":            r"^CPU 0 cumulative IPC:\s*([\d.]+)",
    "L2C_LOAD_MPKI":  r"^L2C LOAD\s+ACCESS:.*MPKI:\s*([\d.]+)",
    "L2C_INSTR_MPKI": r"^L2C INSTRUCTION LOAD MPKI:\s*([\d.]+)",
    "L2C_DATA_MPKI":  r"^L2C DATA LOAD MPKI:\s*([\d.]+)",
    # only dyn_irrip prints these: how many decisions picked each mode
    "EPOCHS_IRRIP":   r"epochs I-RRIP:\s*(\d+)",
    "EPOCHS_SRRIP":   r"epochs SRRIP:\s*(\d+)",
}

# row order in the tables; anything not listed goes at the end
ORDER = ["lru", "rrip", "irrip", "irrip_insonly", "irrip_evictonly",
         "irrip_hit0", "irrip_hit0_ins1"]


def last_match(text, pat):
    m = re.findall(pat, text, re.M)
    return float(m[-1]) if m else float("nan")


def rank(config):
    if config in ORDER:
        return (ORDER.index(config), 0.0)
    if config.startswith("dyn_t"):
        return (len(ORDER), float(config[5:]))
    return (len(ORDER) + 1, 0.0)


rows = []
for f in sorted(glob.glob(os.path.join(RES, "*.txt"))):
    name = os.path.basename(f)[:-4]
    if "_" not in name:
        continue
    config, trace = name.rsplit("_", 1)
    if config.startswith("duel_w"):
        continue
    text = open(f, errors="ignore").read()
    if "ChampSim completed all CPUs" not in text:
        print(f"skipping {f}: the run did not finish")
        continue
    row = {"config": config, "trace": trace}
    row.update({k: last_match(text, p) for k, p in PATTERNS.items()})
    rows.append(row)

if not rows:
    sys.exit(f"no finished result files in {RES}")

df = pd.DataFrame(rows)
if "lru" not in set(df.config):
    sys.exit("no lru runs found, so there is no baseline to compute speedup against")
df["IRRIP_EPOCH_PCT"] = 100.0 * df.EPOCHS_IRRIP / (df.EPOCHS_IRRIP + df.EPOCHS_SRRIP)
base = df[df.config == "lru"].set_index("trace")["IPC"]
df["Speedup"] = df.apply(lambda r: r.IPC / base.get(r.trace, float("nan")), axis=1)
df["_rank"] = df.config.map(rank)
df = df.sort_values(["trace", "_rank"]).drop(columns="_rank")

# one summary row per config: geometric-mean speedup and MPKI summed over the traces
configs = sorted(df.config.unique(), key=rank)
summary = pd.DataFrame([{
    "config": c,
    "geomean_speedup": float(np.exp(np.log(s.Speedup).mean())),
    "sum_load_mpki": s.L2C_LOAD_MPKI.sum(),
    "sum_instr_mpki": s.L2C_INSTR_MPKI.sum(),
    "sum_data_mpki": s.L2C_DATA_MPKI.sum(),
} for c in configs for s in [df[df.config == c]]])


def write_md(fh, table):
    cols = list(table.columns)
    fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
    for _, r in table.iterrows():
        fh.write("| " + " | ".join(f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c])
                                    for c in cols) + " |\n")


df.to_csv(os.path.join(RES, "task2_results.csv"), index=False)
with open(os.path.join(RES, "task2_results.md"), "w") as fh:
    write_md(fh, df)
    fh.write("\n")
    write_md(fh, summary)
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print()
print(summary.to_string(index=False, float_format=lambda x: f"{x:.5f}"))


LABEL = {"lru": "LRU", "rrip": "SRRIP", "irrip": "I-RRIP (final)",
         "irrip_insonly": "Insertion only", "irrip_evictonly": "Eviction only",
         "irrip_hit0": "Ins + Evict (data hit -> 0)",
         "irrip_hit0_ins1": "Ins@1 + Evict (data hit -> 0)"}


def label(c):
    if c in LABEL:
        return LABEL[c]
    return "Dyn I-RRIP (thr " + c[5:] + ")"


def bar_plot(metric, configs, fname, ylabel, title, baseline_line=False):
    sub = df[df.config.isin(configs)]
    if sub.empty:
        return
    piv = sub.pivot(index="trace", columns="config", values=metric)[
        [c for c in configs if c in set(sub.config)]]
    piv.columns = [label(c) for c in piv.columns]
    ax = piv.plot(kind="bar", figsize=(9, 5), edgecolor="grey", rot=0)
    if baseline_line:
        ax.axhline(1.0, color="red", ls="--", lw=1, label="Baseline (LRU)")
    if metric == "Speedup":
        # the bars differ by a few percent at most, so zoom in around 1.0
        lo, hi = piv.min().min(), piv.max().max()
        ax.set_ylim(min(lo, 1.0) - 0.005, max(hi, 1.0) + 0.005)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Traces")
    ax.set_title(title)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    plt.tight_layout()
    plt.savefig(os.path.join(OUT, fname), dpi=150)
    plt.close()


METRICS = [("IPC", "IPC"), ("L2C_LOAD_MPKI", "L2C Load MPKI"),
           ("L2C_INSTR_MPKI", "L2 Instruction Load MPKI"),
           ("L2C_DATA_MPKI", "L2 Data Load MPKI")]

# Task 2A: the static policies
t2a = ["lru", "rrip", "irrip"]
for metric, ylabel in METRICS:
    bar_plot(metric, t2a, f"task2a_{metric}.png", ylabel, f"Task 2A: {ylabel}")
bar_plot("Speedup", t2a, "task2a_speedup.png", "Speedup over LRU",
         "Task 2A: speedup over LRU (no prefetcher)", baseline_line=True)

# Task 2A design ablation, drawn only when all four variants have been run
abl = ["rrip", "irrip_insonly", "irrip_evictonly", "irrip_hit0", "irrip_hit0_ins1", "irrip"]
if set(abl[1:5]) <= set(df.config):
    bar_plot("Speedup", abl, "task2a_ablation_speedup.png", "Speedup over LRU",
             "Task 2A: I-RRIP design ablation", baseline_line=True)
    bar_plot("L2C_INSTR_MPKI", abl, "task2a_ablation_L2C_INSTR_MPKI.png",
             "L2 Instruction Load MPKI", "Task 2A: I-RRIP design ablation")
    bar_plot("L2C_DATA_MPKI", abl, "task2a_ablation_L2C_DATA_MPKI.png",
             "L2 Data Load MPKI", "Task 2A: I-RRIP design ablation")

# Task 2B: the static policies plus the dynamic one at the chosen threshold
DYN_MAIN = os.environ.get("DYN_MAIN", "dyn_t0.25")   # set DYN_MAIN to plot another threshold
t2b = ["lru", "rrip", "irrip", DYN_MAIN]
for metric, ylabel in METRICS:
    bar_plot(metric, t2b, f"task2b_{metric}.png", ylabel, f"Task 2B: {ylabel}")
bar_plot("Speedup", t2b, "task2b_speedup.png", "Speedup over LRU",
         "Task 2B: speedup over LRU (no prefetcher)", baseline_line=True)

# Task 2B: threshold sensitivity study
dyn = [c for c in configs if c.startswith("dyn_t")]
for metric, ylabel in [("Speedup", "Speedup over LRU")] + METRICS[1:] + \
                      [("IRRIP_EPOCH_PCT", "Epochs spent in I-RRIP mode (%)")]:
    bar_plot(metric, dyn, f"task2b_sensitivity_{metric}.png", ylabel,
             f"Dynamic I-RRIP threshold sensitivity: {ylabel}",
             baseline_line=(metric == "Speedup"))

print(f"\nTables: {RES}/task2_results.csv, {RES}/task2_results.md\nPlots:  {OUT}/task2*.png")
