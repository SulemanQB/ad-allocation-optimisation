"""Mixed-integer ad-slot allocation with OR-Tools CBC."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd
from ortools.linear_solver import pywraplp

from .generate_instance import Instance
from .greedy import AllocationResult


@dataclass
class MipSolveInfo:
    status: str
    objective: float
    wall_seconds: float
    mip_gap: float | None


DEFAULT_PENALTY = 0.002  # $ per unmet impression


def solve_mip(
    instance: Instance,
    time_limit_s: float = 30.0,
    penalty: float = DEFAULT_PENALTY,
    hard_target: bool = False,
) -> tuple[AllocationResult, MipSolveInfo]:
    """Solve the allocation MIP with CBC.

    hard_target=True forces every campaign to reach its impression target
    (shortfall fixed to zero); the model may then be infeasible.
    """
    slots = instance.slots.set_index("slot_id")
    campaigns = instance.campaigns.set_index("campaign_id")
    rates = instance.rates[instance.rates["eligible"] == 1].copy()
    if rates.empty:
        empty = AllocationResult(pd.DataFrame(), 0.0, 0.0, "ortools_cbc")
        return empty, MipSolveInfo("INFEASIBLE", 0.0, 0.0, None)

    rates["expected_revenue"] = (
        rates["expected_cpm"] * slots.loc[rates["slot_id"], "impressions"].to_numpy() / 1000.0
    )

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:  # pragma: no cover
        raise RuntimeError("CBC solver unavailable")
    solver.SetTimeLimit(int(time_limit_s * 1000))

    x: dict[tuple[str, str], pywraplp.Variable] = {}
    for _, row in rates.iterrows():
        key = (row["slot_id"], row["campaign_id"])
        x[key] = solver.BoolVar(f"x_{key[0]}_{key[1]}")

    # Slot capacity
    for sid, slot in slots.iterrows():
        vars_s = [x[(sid, cid)] for cid in campaigns.index if (sid, cid) in x]
        if vars_s:
            solver.Add(sum(vars_s) <= int(slot["capacity"]))

    total_impressions = float(slots["impressions"].sum())

    # Soft target: minimise shortfall with a penalty; hard pacing and capacity.
    shortfall = {}
    for cid, camp in campaigns.iterrows():
        delivered = []
        for sid in slots.index:
            if (sid, cid) in x:
                delivered.append(x[(sid, cid)] * float(slots.loc[sid, "impressions"]))
        delivered_expr = sum(delivered) if delivered else 0
        sf_ub = 0.0 if hard_target else float(camp["target_impressions"])
        sf = solver.NumVar(0, sf_ub, f"shortfall_{cid}")
        shortfall[cid] = sf
        solver.Add(delivered_expr + sf >= float(camp["target_impressions"]))
        # Pacing: campaign cannot take more than pacing_max_share of network impressions
        solver.Add(delivered_expr <= float(camp["pacing_max_share"]) * total_impressions)

    revenue = sum(x[k] * float(rates.set_index(["slot_id", "campaign_id"]).loc[k, "expected_revenue"]) for k in x)
    # Prefer revenue; lightly penalise unmet demand so targets matter
    objective = revenue - penalty * sum(shortfall.values())
    solver.Maximize(objective)

    t0 = time.perf_counter()
    status_code = solver.Solve()
    wall = time.perf_counter() - t0
    status_map = {
        pywraplp.Solver.OPTIMAL: "OPTIMAL",
        pywraplp.Solver.FEASIBLE: "FEASIBLE",
        pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
        pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
        pywraplp.Solver.ABNORMAL: "ABNORMAL",
        pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
    }
    status = status_map.get(status_code, str(status_code))

    rows = []
    if status in {"OPTIMAL", "FEASIBLE"}:
        rate_idx = rates.set_index(["slot_id", "campaign_id"])
        for (sid, cid), var in x.items():
            if var.solution_value() > 0.5:
                impr = float(slots.loc[sid, "impressions"])
                rev = float(rate_idx.loc[(sid, cid), "expected_revenue"])
                rows.append(
                    {
                        "slot_id": sid,
                        "campaign_id": cid,
                        "impressions": impr,
                        "revenue": rev,
                        "cpm": float(rate_idx.loc[(sid, cid), "expected_cpm"]),
                    }
                )
    assignments = pd.DataFrame(rows)
    revenue_val = float(assignments["revenue"].sum()) if len(assignments) else 0.0
    delivered = float(assignments["impressions"].sum()) if len(assignments) else 0.0
    fill_rate = delivered / total_impressions if total_impressions else 0.0
    gap = None
    if status == "OPTIMAL":
        gap = 0.0
    result = AllocationResult(assignments, revenue_val, fill_rate, "ortools_cbc")
    info = MipSolveInfo(status, float(solver.Objective().Value()) if status in {"OPTIMAL", "FEASIBLE"} else 0.0, wall, gap)
    return result, info
