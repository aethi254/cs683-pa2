#!/bin/bash
# Run every Task 2 simulation on all three traces, several at a time.
#
# Usage (from anywhere):  ./scripts/run_task2.sh [WARMUP] [SIM] [JOBS]
#   WARMUP and SIM default to 25M instructions each, JOBS to 8 parallel runs.
#   Set SKIP_DONE=1 to skip runs whose output file already finished, which is
#   handy after an interrupted run. Without it every run starts from scratch.
#
# Each run writes results_task2/<config>_<trace>.txt. The configs are:
#   lru, rrip, irrip           Task 2A (LRU is the baseline for speedup)
#   irrip_<variant>            Task 2A design ablation
#   dyn_t<threshold>           Task 2B threshold design, one per threshold
#   duel_w<weight>             Task 2B set-dueling design, one per weight W
# Build the binaries first with ./scripts/build_task2.sh.

cd "$(dirname "$0")/.." || exit 1

WARM=${1:-25000000}
SIM=${2:-25000000}
JOBS=${3:-8}
TRACE_DIR=../Traces     # keep this relative: ChampSim breaks on paths with spaces
OUT=results_task2
TRACES="Trace1 Trace2 Trace3"
STATIC="lru rrip irrip"
ABLATION="irrip_insonly irrip_evictonly irrip_hit0 irrip_hit0_ins1"
THRESHOLDS="0.25 0.40 0.45 0.50 0.60"
WEIGHTS="1 2 4 8 16"

mkdir -p "$OUT"

for t in $TRACES; do
    [ -e "$TRACE_DIR/$t.gz" ] || { echo "missing trace $TRACE_DIR/$t.gz"; exit 1; }
done

bin_of() { ls bin/*-1core-"$1" 2> /dev/null | head -1; }

# One line per run: binary, config name, trace, and an environment setting
# for the dynamic policies ("-" when the policy takes no parameter).
jobs_file=$(mktemp)
trap 'rm -f "$jobs_file"' EXIT
missing=""
add_job() {
    local bin
    bin=$(bin_of "$1")
    if [ -z "$bin" ]; then
        missing="$missing $1"
        return
    fi
    echo "$bin $2 $3 $4" >> "$jobs_file"
}

for t in $TRACES; do
    for cfg in $STATIC $ABLATION; do
        add_job "$cfg" "$cfg" "$t" -
    done
    for th in $THRESHOLDS; do
        add_job dyn_irrip "dyn_t$th" "$t" "IRRIP_THRESHOLD=$th"
    done
    for w in $WEIGHTS; do
        add_job dyn_duel "duel_w$w" "$t" "IRRIP_INSTR_WEIGHT=$w"
    done
done

if [ -n "$missing" ]; then
    echo "no binary for:$(echo "$missing" | tr ' ' '\n' | sort -u | tr '\n' ' ')"
    echo "run ./scripts/build_task2.sh first"
    exit 1
fi

run_one() {
    bin=$1; cfg=$2; t=$3; setting=$4
    out="$OUT/${cfg}_${t}.txt"
    if [ "$SKIP_DONE" = 1 ] && grep -q "ChampSim completed all CPUs" "$out" 2> /dev/null; then
        echo "[skip ] $cfg $t (already finished)"
        return
    fi
    [ "$setting" != "-" ] && export "$setting"
    echo "[start] $cfg $t"
    if "$bin" -warmup_instructions "$WARM" -simulation_instructions "$SIM" \
        -traces "$TRACE_DIR/$t.gz" > "$out" 2>&1; then
        echo "[done ] $cfg $t"
    else
        echo "[FAIL ] $cfg $t, see $out"
    fi
}
export -f run_one
export WARM SIM TRACE_DIR OUT SKIP_DONE

echo "$(wc -l < "$jobs_file") runs, $JOBS at a time, warmup $WARM, sim $SIM"
xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ < "$jobs_file"
echo "all Task 2 runs finished, outputs are in $OUT"
