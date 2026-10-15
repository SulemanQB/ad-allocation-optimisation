"""Sensitivity of the CBC MIP to the shortfall penalty and slot capacity."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .generate_instance import Instance, generate_instance
from .metrics import allocation_metrics
from .mip_ortools import DEFAULT_PENALTY, solve_mip

PENALTY_FACTORS = [0.0, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0]
CAPACITY_SCALES = [0.90, 0.95, 1.00, 1.05, 1.10]


def scale_capacity(instance: Instance, scale: float) -> Instance:
    """Scale slot inventory by `scale`.

    Ad-unit capacity is a small integer (1-3), so a +/-10% change on each slot
    would round away. Instead the *network* capacity is scaled: the total
    number of ad units becomes round(scale * total), with units removed from / added to slots round-robin in slot-id order
    """
    slots = instance.slots.copy()
    caps = slots["capacity"].astype(int).to_numpy().copy()
    total = int(caps.sum())
    delta = int(round(scale * total)) - total
    order = slots.index.to_list()
    i = 0
    while delta != 0 and order:
        idx = order[i % len(order)]
        if delta > 0:
            caps[idx] += 1
            delta -= 1
        elif caps[idx] > 0:
            caps[idx] -= 1
            delta += 1
        i += 1
        if i > 100 * len(order):  # pragma: no cover
            break
    slots["capacity"] = caps
    return replace(instance, slots=slots)


def run_sensitivity(instance: Instance | None = None, time_limit_s: float = 30.0) -> pd.DataFrame:
    inst = instance if instance is not None else generate_instance()
    rows = []
    for f in PENALTY_FACTORS:
        res, info = solve_mip(inst, time_limit_s=time_limit_s, penalty=DEFAULT_PENALTY * f)
        rows.append({"sweep": "shortfall_penalty", "value": DEFAULT_PENALTY * f, "factor": f,
                     "status": info.status, "objective": round(info.objective, 2),
                     **allocation_metrics(inst, res)})
    for s in CAPACITY_SCALES:
        scaled = scale_capacity(inst, s)
        res, info = solve_mip(scaled, time_limit_s=time_limit_s)
        rows.append({"sweep": "slot_capacity", "value": int(scaled.slots["capacity"].sum()), "factor": s,
                     "status": info.status, "objective": round(info.objective, 2),
                     **allocation_metrics(scaled, res)})
    return pd.DataFrame(rows)


def plot_sensitivity(df: pd.DataFrame, out: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return False
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax, sweep, xl in [(axes[0], "shortfall_penalty", "shortfall penalty factor (x 0.002 $/impr)"),
                          (axes[1], "slot_capacity", "network ad-unit capacity scale")]:
        d = df[df["sweep"] == sweep]
        ax.plot(d["factor"], d["revenue"], "o-", color="tab:blue")
        ax.set_xlabel(xl)
        ax.set_ylabel("expected revenue ($)", color="tab:blue")
        if sweep == "shortfall_penalty":
            ax.set_xscale("symlog", linthresh=0.5)
        ax2 = ax.twinx()
        ax2.plot(d["factor"], d["pct_campaigns_at_target"], "s--", color="tab:orange")
        ax2.set_ylabel("% campaigns at target", color="tab:orange")
        ax2.set_ylim(0, 105)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return True


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    df = run_sensitivity()
    df.to_csv(root / "results" / "sensitivity.csv", index=False)
    plot_sensitivity(df, root / "results" / "sensitivity.png")
    print(df.to_string(index=False))
