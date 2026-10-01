#!/bin/bash
# Run all Task 2 simulations in parallel.
# Usage (from the pa2/ directory):  ./scripts/run_task2.sh [WARMUP] [SIM] [JOBS]
WARM=${1:-25000000}
SIM=${2:-25000000}
JOBS=${3:-8}
TRACE_DIR=../Traces            # relative path: ChampSim breaks on paths with spaces
OUT=results/task2
THRESHOLDS="0.25 0.40 0.45 0.50 0.60"

mkdir -p "$OUT"
bin_of() { ls bin/*-1core-"$1" | head -1; }

jobs_file=$(mktemp)
for t in Trace1 Trace2 Trace3; do
    for cfg in lru rrip irrip; do
        echo "$(bin_of $cfg) $cfg $t -" >> "$jobs_file"
    done
    for th in $THRESHOLDS; do
        echo "$(bin_of dyn_irrip) dyn_t$th $t $th" >> "$jobs_file"
    done
done

run_one() {
    bin=$1; cfg=$2; t=$3; th=$4
    [ "$th" != "-" ] && export IRRIP_THRESHOLD=$th
    echo "[start] $cfg $t"
    "$bin" -warmup_instructions "$WARM" -simulation_instructions "$SIM" \
        -traces "$TRACE_DIR/$t.gz" > "$OUT/${cfg}_${t}.txt" 2>&1
    echo "[done ] $cfg $t"
}
export -f run_one
export WARM SIM TRACE_DIR OUT

xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ < "$jobs_file"
rm -f "$jobs_file"
echo "All Task 2 runs finished -> $OUT"
