# Ad-slot allocation optimisation

A small media / ad-yield inventory allocation demo: a mixed-integer program (MIP) that allocates ad inventory across campaigns under capacity, pacing, and demand targets, compared against a simple greedy baseline.

Synthetic data only; not from any commercial dataset. All numbers below come from the bundled synthetic generator.

## What it models

- Slots with channel, daypart, impressions, and multi-ad capacity
- Campaigns with impression targets, max CPM, priority, and a pacing share cap
- Eligibility and expected CPM per slot-campaign pair
- Objective: maximise expected revenue, with a soft penalty on unmet campaign targets

## Solvers

| Method | Backend |
|--------|---------|
| Greedy baseline | Highest expected-revenue eligible assignment under capacity / pacing / remaining demand |
| MIP | Google OR-Tools CBC (`ortools`) |

Optional `gurobipy` support is not wired yet (needs a Gurobi licence). Modelling ideas transfer 1:1.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.run_benchmark
pytest -q
```

## Latest synthetic benchmark (seed 42, 40 slots, 12 campaigns)

From `results/benchmark.json` after `python -m src.run_benchmark`:

| Metric | Greedy | OR-Tools CBC |
|--------|--------|--------------|
| Expected revenue | 89,164.09 | 165,623.57 |
| Revenue vs greedy | - | **+85.75%** |
| Assignments | 35 | 79 |
| Status / wall time | - | OPTIMAL / 0.45 s |

The +85.75% is the MIP's expected revenue relative to a simple greedy baseline on this one synthetic instance (seed 42, 40 slots, 12 campaigns). It shows how much a naive heuristic can leave on the table in this toy model; it is not a real-world or production revenue gain. Wall time varies slightly between machines and runs.

Capacity can be greater than one ad per slot, so assigned impressions can exceed unique slot impressions.

## Layout

```
src/generate_instance.py  # synthetic slots, campaigns, rates
src/greedy.py             # baseline
src/mip_ortools.py        # CBC MIP
src/run_benchmark.py      # write results/
data/                     # regenerated CSVs
results/                  # benchmark.json + assignment CSVs
tests/                    # capacity + revenue regression checks
```

## Honest limits

- Synthetic data only; no makegoods, guaranteed vs non-guaranteed split, or live sell-out curves yet.
- No CPLEX.
- Do not cite these figures as production results.
