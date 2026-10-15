"""Run all methods on the synthetic seed-42 instance and write results/."""

from __future__ import annotations

import json
from pathlib import Path

from .generate_instance import generate_instance, write_instance
from .greedy import greedy_allocate
from .metrics import allocation_metrics
from .mip_gurobi import gurobi_available, solve_mip_gurobi
from .mip_ortools import solve_mip
from .sensitivity import plot_sensitivity, run_sensitivity


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    res_dir = root / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    inst = generate_instance()
    write_instance(inst, root / "data")

    runs = [
        (greedy_allocate(inst), None),
        (greedy_allocate(inst, stop_at_target=False), None),
    ]
    mip, info = solve_mip(inst)
    runs.append((mip, info))
    hard, hinfo = solve_mip(inst, hard_target=True)
    hard.method = "ortools_cbc_hard_target"
    runs.append((hard, hinfo))
    if gurobi_available():
        g, ginfo = solve_mip_gurobi(inst)
        runs.append((g, ginfo))
        gh, ghinfo = solve_mip_gurobi(inst, hard_target=True)
        gh.method = "gurobi_hard_target"
        runs.append((gh, ghinfo))

    methods = []
    for res, si in runs:
        row = allocation_metrics(inst, res)
        if si is not None:
            row.update(status=si.status, objective=round(si.objective, 2),
                       wall_seconds=round(si.wall_seconds, 4),
                       mip_gap=None if si.mip_gap is None else round(si.mip_gap, 6))
        methods.append(row)
        res.assignments.to_csv(res_dir / f"{res.method}_assignments.csv", index=False)

    summary = {
        "n_slots": len(inst.slots),
        "n_campaigns": len(inst.campaigns),
        "n_binary_vars": int((inst.rates["eligible"] == 1).sum()),
        "methods": methods,
        "note": "Synthetic instance only; not from any commercial dataset.",
    }
    (res_dir / "benchmark.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    sens = run_sensitivity(inst)
    sens.to_csv(res_dir / "sensitivity.csv", index=False)
    plot_sensitivity(sens, res_dir / "sensitivity.png")
    print(json.dumps(summary, indent=2))
    print(sens.to_string(index=False))


if __name__ == "__main__":
    main()
