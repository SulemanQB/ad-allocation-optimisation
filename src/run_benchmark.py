"""Run greedy vs OR-Tools MIP on the synthetic instance and print a summary."""

from __future__ import annotations

import json
from pathlib import Path

from .generate_instance import generate_instance, write_instance
from .greedy import greedy_allocate
from .mip_ortools import solve_mip


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    inst = generate_instance()
    write_instance(inst, data_dir)

    greedy = greedy_allocate(inst)
    mip, info = solve_mip(inst)

    gain = mip.revenue - greedy.revenue
    gain_pct = (gain / greedy.revenue * 100.0) if greedy.revenue else 0.0
    summary = {
        "greedy_revenue": round(greedy.revenue, 2),
        "mip_revenue": round(mip.revenue, 2),
        "revenue_gain": round(gain, 2),
        "revenue_gain_pct": round(gain_pct, 2),
        "greedy_fill_rate": round(greedy.fill_rate, 4),
        "mip_fill_rate": round(mip.fill_rate, 4),
        "mip_status": info.status,
        "mip_wall_seconds": round(info.wall_seconds, 4),
        "n_slots": len(inst.slots),
        "n_campaigns": len(inst.campaigns),
        "n_greedy_assignments": len(greedy.assignments),
        "n_mip_assignments": len(mip.assignments),
        "note": "Synthetic instance only; not from any commercial dataset.",
    }
    out = root / "results" / "benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    greedy.assignments.to_csv(root / "results" / "greedy_assignments.csv", index=False)
    mip.assignments.to_csv(root / "results" / "mip_assignments.csv", index=False)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
