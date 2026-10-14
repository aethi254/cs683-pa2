#!/bin/bash
# Reproduce all of Task 1 in one go: build the three L1D prefetcher configurations (LRU at the L2C),
# run them on all three traces, then build the tables and plots.
#
# Usage (from anywhere):  ./scripts/task1_all.sh
#
# Runs, written to results/<config>/<trace>.txt:
#   baseline    no L1D prefetcher
#   ip_stride   the provided IP-stride prefetcher (Task 1A)
#   spp         our Stride Pattern Prefetcher (Task 1B)

cd "$(dirname "$0")/.." || exit 1

WARM=25000000
SIM=25000000
TRACE_DIR=../traces    # relative, and the same folder name as every other task: ChampSim seeds its page mapping from it
mkdir -p results/logs

# same compiler as the course setup and the other tasks
if [ -z "$CXX" ] && command -v g++-7 > /dev/null; then
    export CXX=g++-7
fi

# the builds run one after another because build_champsim.sh runs `make clean` and they all share obj/
for cfg in baseline ip_stride spp; do
    pf=$cfg
    [ "$cfg" = baseline ] && pf=no
    if ! ./build_champsim.sh "$pf" lru "$cfg" > "results/logs/build_$cfg.log" 2>&1; then
        echo "$cfg: build failed, see results/logs/build_$cfg.log"
        exit 1
    fi
    echo "$cfg: built"
done

# all nine runs at once
for cfg in baseline ip_stride spp; do
    mkdir -p "results/$cfg"
    for t in Trace1 Trace2 Trace3; do
        ./bin/*-1core-"$cfg" -warmup_instructions $WARM -simulation_instructions $SIM \
            -traces "$TRACE_DIR/$t.gz" > "results/$cfg/$t.txt" 2>&1 &
    done
done
failed=0
for job in $(jobs -p); do
    wait "$job" || failed=1
done
if [ $failed = 1 ]; then
    echo "some simulations failed, see results/<config>/<trace>.txt"
    exit 1
fi
echo "all Task 1 runs finished"
python3 scripts/parse_task1.py
