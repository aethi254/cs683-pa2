# ChampSim

ChampSim is a trace-based simulator for microarchitecture research.

## PA2: reproducing our results

All runs use GCC 7 (`g++-7`), 25M warmup + 25M simulated instructions, and the traces in a folder named `traces` next to this repo (`../traces/Trace1.gz`, ...). Keep that folder name: ChampSim derives its random seed, and with it the virtual-to-physical page mapping, from the name of the folder that holds the trace, so `../Traces/` gives slightly different numbers. Each script below builds its binaries, runs all its simulations, and writes tables (`.md`, `.csv`) and plots (`plots/`) into its results folder.

| Task | Code | Command | Results |
|---|---|---|---|
| 1A, 1B | `prefetcher/ip_stride.l1d_pref`, `prefetcher/spp.l1d_pref` | `./scripts/task1_all.sh` | `results/` |
| 2A | `replacement/irrip.l2c_repl` (+ ablation variants `irrip_*.l2c_repl`) | `./scripts/task2_all.sh` | `results_task2/` |
| 2B | `replacement/dyn_irrip.l2c_repl` (threshold design), `replacement/dyn_duel.l2c_repl` (set-dueling design) | `./scripts/task2_all.sh` | `results_task2/` |
| 3 | `replacement/dyn_irrip.l2c_repl` in its prefetch-aware mode, with `spp` at the L1D | `./scripts/task3_all.sh` | `results_task3/` |

**Task 3 needs `IRRIP_PF_AWARE=1`.** `dyn_irrip.l2c_repl` contains both Task 2B and Task 3. Without the environment variable it runs as in Task 2B. To run the Task 3 policy by hand:

```bash
./build_champsim.sh spp dyn_irrip spp_dyn_irrip
IRRIP_PF_AWARE=1 ./bin/hashed_perceptron-no-spp-no-no-no-no-no-lru-lru-lru-dyn_irrip-lru-lru-lru-lru-1core-spp_dyn_irrip \
    -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ../traces/Trace1.gz
```

Other run-time parameters (read from the environment, so one binary covers each sensitivity study):

| Variable | Policy | Default | Meaning |
|---|---|---|---|
| `IRRIP_THRESHOLD` | `dyn_irrip` | 0.25 (0.55 with `IRRIP_PF_AWARE=1`) | ratio threshold for choosing I-RRIP |
| `IRRIP_PF_AWARE` | `dyn_irrip` | 0 | 1 turns on the Task 3 prefetch-aware mode |
| `IRRIP_INSTR_WEIGHT` | `dyn_duel` | 4 | cost W of an instruction miss in the set duel |

Useful trace links:
- Traces (access requires an LDAP ID): https://drive.google.com/drive/folders/1zYchkn-M1auZp_l5wRkIzAcDYPkNtW3H?usp=sharing
- ChampSim wiki: https://champsim.github.io/ChampSim/master/index.html

## Clone the repository

```bash
git clone https://github.com/cs683-iitb-autumn-2026/pa2.git
```

## Compile

To compile ChampSim, specify three parameters: the L1D prefetcher, the L2C replacement policy, and the binary name.

For example, `./build_champsim.sh no lru baseline` builds a single-core processor with a hashed perceptron branch predictor, no L1D data prefetcher, and the LRU replacement policy for the L2C.

You can give the binary any name. Custom names help distinguish binaries that use the same configuration.

```bash
./build_champsim.sh ${L1D_PREFETCHER} ${L2C_REPLACEMENT} ${BINARY_NAME}

./build_champsim.sh no lru baseline
```

## Run simulation

```bash
./bin/[BINARY] -warmup_instructions [N_WARM] -simulation_instructions [N_SIM] -traces [TRACE_DIR]/[TRACE]
./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ../traces/trace1.champsimtrace.xz
```

Where:
- `${BINARY}`: ChampSim binary compiled by `build_champsim.sh` (for example, `hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline`)
- `${N_WARM}`: number of instructions for the warmup period (25 million)
- `${N_SIM}`: number of instructions for the detailed simulation (25 million)
- `${TRACE_DIR}`: directory containing the trace (for example, `../traces/`)
- `${TRACE}`: name of the trace (for example, `trace1.champsimtrace.xz`)

## Evaluate the simulation

ChampSim measures IPC (instructions per cycle) as its main performance metric. It also prints other useful metrics at the end of each simulation.

## Install GCC 7 on Ubuntu

```bash
sudo apt update
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
vim /etc/apt/sources.list
```

Update the last line with:

```bash
deb [arch=amd64] http://archive.ubuntu.com/ubuntu focal main universe
```

Then run:

```bash
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
sudo apt-get install gcc-7
sudo apt-get install g++-7
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-7 0
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-7 0
```

If GCC and G++ are already present in `/usr/bin`, configure the alternatives using:

```bash
sudo update-alternatives --config g++
sudo update-alternatives --config gcc
```

