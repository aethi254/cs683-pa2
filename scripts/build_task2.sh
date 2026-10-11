#!/bin/bash
# Build every ChampSim binary that Task 2 needs: no L1D prefetcher, and one
# binary per L2C replacement policy.
#
# Usage (from anywhere):  ./scripts/build_task2.sh [policy ...]
#   With no arguments it builds all the policies listed in ALL_POLICIES.
#   Each build log goes to results_task2/logs/build_<policy>.log.
#
# The builds run one after another because build_champsim.sh runs `make clean`
# and every binary shares obj/. Two builds at the same time would break each other.

cd "$(dirname "$0")/.." || exit 1

LOGS=results_task2/logs
mkdir -p "$LOGS"

ALL_POLICIES="lru rrip irrip irrip_insonly irrip_evictonly irrip_hit0 irrip_hit0_ins1 dyn_irrip dyn_duel"
POLICIES=${*:-$ALL_POLICIES}

# The Makefile compiles with $(CXX). The course setup uses GCC 7, and the
# committed results were produced with it, so use g++-7 unless CXX is already set.
if [ -z "$CXX" ]; then
    if command -v g++-7 > /dev/null; then
        export CXX=g++-7
    else
        echo "warning: g++-7 not found, building with the default g++ (results may differ slightly)"
    fi
fi
export MAKEFLAGS=${MAKEFLAGS:--j$(nproc)}
echo "compiler: $(${CXX:-g++} --version | head -1)"

failed=""
for p in $POLICIES; do
    if [ ! -f "replacement/$p.l2c_repl" ]; then
        echo "$p: replacement/$p.l2c_repl does not exist"
        failed="$failed $p"
        continue
    fi
    if ./build_champsim.sh no "$p" "$p" > "$LOGS/build_$p.log" 2>&1; then
        echo "$p: built"
    else
        echo "$p: FAILED, see $LOGS/build_$p.log"
        failed="$failed $p"
    fi
done

if [ -n "$failed" ]; then
    echo "these builds failed:$failed"
    exit 1
fi
echo "all builds finished, binaries are in bin/"
