#!/usr/bin/env python3
"""Parse Task 2 ChampSim outputs -> CSV/Markdown tables + bar plots.

Expects files named results/task2/<config>_<trace>.txt, e.g. irrip_Trace1.txt,
dyn_t0.25_Trace2.txt. Speedup is computed against the 'lru' run of the same trace.
"""
import glob
import os
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

RES = sys.argv[1] if len(sys.argv) > 1 else "results/task2"
OUT = os.path.join(RES, "plots")
os.makedirs(OUT, exist_ok=True)

PATTERNS = {
    "IPC":            r"^CPU 0 cumulative IPC:\s*([\d.]+)",
    "L2C_LOAD_MPKI":  r"^L2C LOAD\s+ACCESS:.*MPKI:\s*([\d.]+)",
    "L2C_INSTR_MPKI": r"^L2C INSTRUCTION LOAD MPKI:\s*([\d.]+)",
    "L2C_DATA_MPKI":  r"^L2C DATA LOAD MPKI:\s*([\d.]+)",
    # printed only by dyn_irrip: how many decision epochs chose each mode
    "EPOCHS_IRRIP":   r"epochs I-RRIP:\s*(\d+)",
    "EPOCHS_SRRIP":   r"epochs SRRIP:\s*(\d+)",
}


def last_match(text, pat):
    m = re.findall(pat, text, re.M)
    return float(m[-1]) if m else float("nan")


rows = []
for f in sorted(glob.glob(os.path.join(RES, "*.txt"))):
    name = os.path.basename(f)[:-4]
    config, trace = name.rsplit("_", 1)
    text = open(f, errors="ignore").read()
    row = {"config": config, "trace": trace}
    row.update({k: last_match(text, p) for k, p in PATTERNS.items()})
    rows.append(row)

if not rows:
    sys.exit(f"no result files in {RES}")

df = pd.DataFrame(rows)
df["IRRIP_EPOCH_PCT"] = 100.0 * df.EPOCHS_IRRIP / (df.EPOCHS_IRRIP + df.EPOCHS_SRRIP)
base = df[df.config == "lru"].set_index("trace")["IPC"]
df["Speedup"] = df.apply(lambda r: r.IPC / base.get(r.trace, float("nan")), axis=1)
df = df.sort_values(["trace", "config"])

df.to_csv(os.path.join(RES, "task2_results.csv"), index=False)
with open(os.path.join(RES, "task2_results.md"), "w") as fh:
    cols = list(df.columns)
    fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
    for _, r in df.iterrows():
        fh.write("| " + " | ".join(f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c]) for c in cols) + " |\n")
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


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
        # differences are a few percent: zoom in around 1.0 so they are visible
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

# Task 2A: static policies only
t2a = ["lru", "rrip", "irrip"]
for metric, ylabel in METRICS:
    bar_plot(metric, t2a, f"task2a_{metric}.png", ylabel, f"Task 2A: {ylabel}")
bar_plot("Speedup", t2a, "task2a_speedup.png", "Speedup over LRU",
         "Task 2A: speedup over LRU (no prefetcher)", baseline_line=True)

# Task 2A design ablation (only if the variant runs exist, see the guide)
abl = ["rrip", "irrip_insonly", "irrip_evictonly", "irrip_hit0", "irrip_hit0_ins1", "irrip"]
if set(abl[1:5]) <= set(df.config):
    bar_plot("Speedup", abl, "task2a_ablation_speedup.png", "Speedup over LRU",
             "Task 2A: I-RRIP design ablation", baseline_line=True)
    bar_plot("L2C_INSTR_MPKI", abl, "task2a_ablation_L2C_INSTR_MPKI.png",
             "L2 Instruction Load MPKI", "Task 2A: I-RRIP design ablation")
    bar_plot("L2C_DATA_MPKI", abl, "task2a_ablation_L2C_DATA_MPKI.png",
             "L2 Data Load MPKI", "Task 2A: I-RRIP design ablation")

# Task 2B: add the dynamic policy at the chosen threshold
DYN_MAIN = os.environ.get("DYN_MAIN", "dyn_t0.25")   # threshold shown in the Task 2B plots
t2b = ["lru", "rrip", "irrip", DYN_MAIN]
for metric, ylabel in METRICS:
    bar_plot(metric, t2b, f"task2b_{metric}.png", ylabel, f"Task 2B: {ylabel}")
bar_plot("Speedup", t2b, "task2b_speedup.png", "Speedup over LRU",
         "Task 2B: speedup over LRU (no prefetcher)", baseline_line=True)

# Task 2B: threshold sensitivity study
dyn = sorted([c for c in df.config.unique() if c.startswith("dyn_t")],
             key=lambda c: float(c[5:]))
for metric, ylabel in [("Speedup", "Speedup over LRU")] + METRICS[1:] + \
                      [("IRRIP_EPOCH_PCT", "Epochs spent in I-RRIP mode (%)")]:
    bar_plot(metric, dyn, f"task2b_sensitivity_{metric}.png", ylabel,
             f"Dynamic I-RRIP threshold sensitivity: {ylabel}",
             baseline_line=(metric == "Speedup"))

print(f"\nTables: {RES}/task2_results.csv, {RES}/task2_results.md\nPlots : {OUT}/")
