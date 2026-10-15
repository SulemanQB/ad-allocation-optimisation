"""Same allocation MIP as mip_ortools.py, solved with Gurobi (gurobipy).

The pip-installed gurobipy ships a size-limited licence (2000 variables /
2000 linear constraints), which is enough for the bundled seed-42 instance.
"""

from __future__ import annotations

import time

import pandas as pd

from .generate_instance import Instance
from .greedy import AllocationResult
from .mip_ortools import DEFAULT_PENALTY, MipSolveInfo

try:  # optional dependency
    import gurobipy as gp
    from gurobipy import GRB
except ImportError:  # pragma: no cover
    gp = None
    GRB = None


def gurobi_available() -> bool:
    return gp is not None


def solve_mip_gurobi(
    instance: Instance,
    time_limit_s: float = 30.0,
    penalty: float = DEFAULT_PENALTY,
    hard_target: bool = False,
) -> tuple[AllocationResult, MipSolveInfo]:
    if gp is None:  # pragma: no cover
        raise RuntimeError("gurobipy is not installed")
    slots = instance.slots.set_index("slot_id")
    campaigns = instance.campaigns.set_index("campaign_id")
    rates = instance.rates[instance.rates["eligible"] == 1].copy()
    if rates.empty:
        return AllocationResult(pd.DataFrame(), 0.0, 0.0, "gurobi"), MipSolveInfo("INFEASIBLE", 0.0, 0.0, None)
    rates["expected_revenue"] = (
        rates["expected_cpm"] * slots.loc[rates["slot_id"], "impressions"].to_numpy() / 1000.0
    )
    rate_idx = rates.set_index(["slot_id", "campaign_id"])
    total_impressions = float(slots["impressions"].sum())

    env = gp.Env(empty=True)
    env.setParam("OutputFlag", 0)
    env.start()
    m = gp.Model("ad_allocation", env=env)
    m.Params.TimeLimit = time_limit_s

    keys = list(rate_idx.index)
    x = m.addVars(keys, vtype=GRB.BINARY, name="x")

    for sid, slot in slots.iterrows():
        vs = [x[(sid, cid)] for cid in campaigns.index if (sid, cid) in x]
        if vs:
            m.addConstr(gp.quicksum(vs) <= int(slot["capacity"]), name=f"cap_{sid}")

    shortfall = {}
    for cid, camp in campaigns.iterrows():
        delivered = gp.quicksum(
            x[(sid, cid)] * float(slots.loc[sid, "impressions"]) for sid in slots.index if (sid, cid) in x
        )
        target = float(camp["target_impressions"])
        sf = m.addVar(lb=0.0, ub=0.0 if hard_target else target, name=f"shortfall_{cid}")
        shortfall[cid] = sf
        m.addConstr(delivered + sf >= target, name=f"target_{cid}")
        m.addConstr(delivered <= float(camp["pacing_max_share"]) * total_impressions, name=f"pace_{cid}")

    revenue = gp.quicksum(x[k] * float(rate_idx.loc[k, "expected_revenue"]) for k in keys)
    m.setObjective(revenue - penalty * gp.quicksum(shortfall.values()), GRB.MAXIMIZE)

    t0 = time.perf_counter()
    m.optimize()
    wall = time.perf_counter() - t0

    status_map = {GRB.OPTIMAL: "OPTIMAL", GRB.INFEASIBLE: "INFEASIBLE", GRB.INF_OR_UNBD: "INFEASIBLE",
                  GRB.UNBOUNDED: "UNBOUNDED", GRB.TIME_LIMIT: "FEASIBLE" if m.SolCount else "NOT_SOLVED"}
    status = status_map.get(m.Status, str(m.Status))

    rows = []
    if m.SolCount:
        for (sid, cid), var in x.items():
            if var.X > 0.5:
                rows.append(
                    {
                        "slot_id": sid,
                        "campaign_id": cid,
                        "impressions": float(slots.loc[sid, "impressions"]),
                        "revenue": float(rate_idx.loc[(sid, cid), "expected_revenue"]),
                        "cpm": float(rate_idx.loc[(sid, cid), "expected_cpm"]),
                    }
                )
    assignments = pd.DataFrame(rows)
    rev = float(assignments["revenue"].sum()) if len(assignments) else 0.0
    delivered_total = float(assignments["impressions"].sum()) if len(assignments) else 0.0
    gap = float(m.MIPGap) if m.SolCount else None
    obj = float(m.ObjVal) if m.SolCount else 0.0
    m.dispose()
    env.dispose()
    return (
        AllocationResult(assignments, rev, delivered_total / total_impressions, "gurobi"),
        MipSolveInfo(status, obj, wall, gap),
    )
