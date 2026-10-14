#!/bin/bash
# Reproduce all of Task 3 in one go: build SPP (L1D) + dynamic I-RRIP (L2C), run it on all three
# traces, then build the tables and plots. Everything it creates goes into results_task3/.
#
# Usage (from anywhere):  ./scripts/task3_all.sh
#   JOBS=n sets how many simulations run at once (default 8).
#
# Runs (one binary, the mode is picked with environment variables):
#   spp_dyn             SPP + dynamic I-RRIP exactly as in Task 2B (IRRIP_PF_AWARE=0, threshold 0.25)
#   spp_pfdyn_t<thr>    SPP + prefetch-aware dynamic I-RRIP (IRRIP_PF_AWARE=1), one per threshold
# The final Task 3 configuration is spp_pfdyn_t0.55. The references (no prefetcher + LRU, SPP + LRU,
# and dynamic I-RRIP without a prefetcher) are read from results/ and results_task2/.

cd "$(dirname "$0")/.." || exit 1

WARM=25000000
SIM=25000000
JOBS=${JOBS:-8}
TRACE_DIR=../traces    # relative, and the same folder name as every other task: ChampSim seeds its page mapping from it
OUT=results_task3
THRESHOLDS="0.25 0.45 0.50 0.55 0.60"
mkdir -p "$OUT/logs"

# same compiler as the course setup and the earlier tasks
if [ -z "$CXX" ] && command -v g++-7 > /dev/null; then
    export CXX=g++-7
fi
if ! ./build_champsim.sh spp dyn_irrip spp_dyn_irrip > "$OUT/logs/build.log" 2>&1; then
    echo "build failed, see $OUT/logs/build.log"
    exit 1
fi
BIN=$(ls bin/*-1core-spp_dyn_irrip)

run_one() {
    cfg=$1; t=$2; shift 2
    if env "$@" "$BIN" -warmup_instructions "$WARM" -simulation_instructions "$SIM" \
        -traces "$TRACE_DIR/$t.gz" > "$OUT/${cfg}_$t.txt" 2>&1; then
        echo "[done ] $cfg $t"
    else
        echo "[FAIL ] $cfg $t, see $OUT/${cfg}_$t.txt"
    fi
}
export -f run_one
export BIN WARM SIM TRACE_DIR OUT

for t in Trace1 Trace2 Trace3; do
    echo "spp_dyn $t IRRIP_PF_AWARE=0"
    for th in $THRESHOLDS; do
        echo "spp_pfdyn_t$th $t IRRIP_PF_AWARE=1 IRRIP_THRESHOLD=$th"
    done
done | xargs -P "$JOBS" -L 1 bash -c 'run_one "$@"' _ | tee "$OUT/logs/run.log"

if grep -q "^\[FAIL" "$OUT/logs/run.log"; then
    echo "some simulations failed, tables were not rebuilt"
    exit 1
fi
python3 scripts/parse_task3.py
