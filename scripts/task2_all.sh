#!/bin/bash
# Reproduce all of Task 2 in one go: build the binaries, run the simulations,
# then rebuild the tables and plots. Everything it creates goes into results_task2/.
#
# Usage (from anywhere):  ./scripts/task2_all.sh [WARMUP] [SIM] [JOBS]
#   The arguments are passed to run_task2.sh (defaults: 25M, 25M, 8 jobs).
#   SKIP_DONE=1 also works here and skips simulations that already finished.
#   Set SKIP_BUILD=1 to reuse the binaries already in bin/.
#
# The full set is 51 simulations (17 configs x 3 traces). With 8 jobs on a
# 16-thread machine that takes roughly 20 minutes, plus a few minutes of builds.
# The build logs and the simulation progress log go to results_task2/logs/.

set -eo pipefail
cd "$(dirname "$0")/.."
mkdir -p results_task2/logs

if [ "$SKIP_BUILD" != 1 ]; then
    ./scripts/build_task2.sh
fi
./scripts/run_task2.sh "$@" 2>&1 | tee results_task2/logs/run_task2.log
if grep -q "^\[FAIL" results_task2/logs/run_task2.log; then
    echo "some simulations failed (see the [FAIL ] lines above), tables were not rebuilt"
    exit 1
fi
python3 scripts/parse_task2.py results_task2
python3 scripts/plot_duel.py results_task2
echo "Task 2 is done: tables in results_task2/*.md, plots in results_task2/plots/, logs in results_task2/logs/"
