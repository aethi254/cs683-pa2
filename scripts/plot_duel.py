#!/usr/bin/env python3
"""Tables + plots for the set-dueling Dynamic I-RRIP (dyn_duel) runs.

Reads results/task2/duel_w<W>_<trace>.txt together with the lru, rrip, irrip and
dyn_t0.25 runs from Step 5, and writes:
  results/task2/duel_results.csv / duel_results.md
  results/task2/plots/duel_*.png
Speedup is computed against the 'lru' run of the same trace.
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

RES = sys.argv[1] if len(sys.argv) > 1 else "results/task2"
OUT = os.path.join(RES, "plots")
os.makedirs(OUT, exist_ok=True)
FINAL_W = os.environ.get("DUEL_FINAL", "duel_w8")   # weight shown in the comparison plots

PATTERNS = {
    "IPC":            r"^CPU 0 cumulative IPC:\s*([\d.]+)",
    "L2C_LOAD_MPKI":  r"^L2C LOAD\s+ACCESS:.*MPKI:\s*([\d.]+)",
    "L2C_INSTR_MPKI": r"^L2C INSTRUCTION LOAD MPKI:\s*([\d.]+)",
    "L2C_DATA_MPKI":  r"^L2C DATA LOAD MPKI:\s*([\d.]+)",
    # printed only by dyn_duel
    "IRRIP_FILL_PCT": r"follower fills in I-RRIP mode:\s*([\d.]+)%",
    "MODE_SWITCHES":  r"DUEL instr weight:.*mode switches:\s*(\d+)",
}


def last_match(text, pat):
    m = re.findall(pat, text, re.M)
    return float(m[-1]) if m else float("nan")


rows = []
for f in sorted(glob.glob(os.path.join(RES, "*.txt"))):
    config, trace = os.path.basename(f)[:-4].rsplit("_", 1)
    if not (config.startswith("duel_w") or config in ("lru", "rrip", "irrip", "dyn_t0.25")):
        continue
    text = open(f, errors="ignore").read()
    row = {"config": config, "trace": trace}
    row.update({k: last_match(text, p) for k, p in PATTERNS.items()})
    rows.append(row)

df = pd.DataFrame(rows)
if df.empty or not df.config.str.startswith("duel_w").any():
    sys.exit(f"no duel_w*_Trace*.txt files in {RES}")
base = df[df.config == "lru"].set_index("trace")["IPC"]
df["Speedup"] = df.apply(lambda r: r.IPC / base.get(r.trace, float("nan")), axis=1)
df = df.sort_values(["trace", "config"])
df.to_csv(os.path.join(RES, "duel_results.csv"), index=False)

weights = sorted([c for c in df.config.unique() if c.startswith("duel_w")], key=lambda c: int(c[6:]))
order = ["lru", "rrip", "irrip", "dyn_t0.25"] + weights
LABEL = {"lru": "LRU", "rrip": "SRRIP", "irrip": "I-RRIP (static)",
         "dyn_t0.25": "Dyn I-RRIP (threshold 0.25)"}


def label(c):
    return LABEL.get(c, "Dyn I-RRIP duel (W=" + c[6:] + ")")


# summary: geometric-mean speedup and summed MPKI over the traces
summary = []
for c in order:
    s = df[df.config == c]
    if s.empty:
        continue
    summary.append({"config": c, "geomean_speedup": float(np.exp(np.log(s.Speedup).mean())),
                    "sum_load_mpki": s.L2C_LOAD_MPKI.sum(), "sum_instr_mpki": s.L2C_INSTR_MPKI.sum(),
                    "sum_data_mpki": s.L2C_DATA_MPKI.sum()})
summary = pd.DataFrame(summary)

with open(os.path.join(RES, "duel_results.md"), "w") as fh:
    for table in (df, summary):
        cols = list(table.columns)
        fh.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for _, r in table.iterrows():
            fh.write("| " + " | ".join(f"{r[c]:.4f}" if isinstance(r[c], float) else str(r[c])
                                        for c in cols) + " |\n")
        fh.write("\n")
print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
print()
print(summary.to_string(index=False, float_format=lambda x: f"{x:.5f}"))


def bar_plot(metric, configs, fname, ylabel, title, baseline_line=False):
    sub = df[df.config.isin(configs)]
    piv = sub.pivot(index="trace", columns="config", values=metric)[
        [c for c in configs if c in set(sub.config)]]
    piv.columns = [label(c) for c in piv.columns]
    ax = piv.plot(kind="bar", figsize=(9, 5), edgecolor="grey", rot=0)
    if baseline_line:
        ax.axhline(1.0, color="red", ls="--", lw=1, label="Baseline (LRU)")
    if metric == "Speedup":
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

# final set-dueling policy against everything else
cmp_cfg = ["lru", "rrip", "irrip", "dyn_t0.25", FINAL_W]
bar_plot("Speedup", cmp_cfg, "duel_speedup.png", "Speedup over LRU",
         "Set-dueling Dynamic I-RRIP: speedup over LRU", baseline_line=True)
for metric, ylabel in METRICS:
    bar_plot(metric, cmp_cfg, f"duel_{metric}.png", ylabel, f"Set-dueling Dynamic I-RRIP: {ylabel}")

# sensitivity study over the instruction-miss weight W
for metric, ylabel in [("Speedup", "Speedup over LRU")] + METRICS[1:] + \
                      [("IRRIP_FILL_PCT", "Follower fills in I-RRIP mode (%)")]:
    bar_plot(metric, weights, f"duel_sensitivity_{metric}.png", ylabel,
             f"Set-dueling sensitivity to W: {ylabel}", baseline_line=(metric == "Speedup"))

print(f"\nTables: {RES}/duel_results.csv, {RES}/duel_results.md\nPlots : {OUT}/duel_*.png")
