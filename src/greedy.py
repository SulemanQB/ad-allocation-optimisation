"""Greedy baseline: assign highest expected-revenue eligible campaigns per slot."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .generate_instance import Instance


@dataclass
class AllocationResult:
    assignments: pd.DataFrame
    revenue: float
    fill_rate: float
    method: str


def greedy_allocate(instance: Instance, stop_at_target: bool = True) -> AllocationResult:
    """Greedy by expected revenue.

    stop_at_target=False is the "fair" baseline: campaigns keep buying past
    their target (subject only to capacity and pacing), like the MIP may.
    """
    slots = instance.slots.set_index("slot_id")
    campaigns = instance.campaigns.set_index("campaign_id")
    rates = instance.rates[instance.rates["eligible"] == 1].copy()
    rates["expected_revenue"] = (
        rates["expected_cpm"] * slots.loc[rates["slot_id"], "impressions"].to_numpy() / 1000.0
    )
    rates = rates.sort_values("expected_revenue", ascending=False)

    remaining_capacity = slots["capacity"].astype(int).to_dict()
    remaining_target = campaigns["target_impressions"].astype(float).to_dict()
    total_impressions = float(slots["impressions"].sum())
    campaign_impr: dict[str, float] = {c: 0.0 for c in remaining_target}
    rows: list[dict] = []

    for _, row in rates.iterrows():
        sid = row["slot_id"]
        cid = row["campaign_id"]
        if remaining_capacity[sid] <= 0:
            continue
        if stop_at_target and remaining_target[cid] <= 0:
            continue
        camp = campaigns.loc[cid]
        impr = float(slots.loc[sid, "impressions"])
        # Pacing: reject if this assignment would push the campaign past its cap
        # (same constraint as the MIP).
        if (campaign_impr[cid] + impr) / total_impressions > float(camp["pacing_max_share"]):
            continue
        rev = float(row["expected_revenue"])
        rows.append(
            {
                "slot_id": sid,
                "campaign_id": cid,
                "impressions": impr,
                "revenue": rev,
                "cpm": float(row["expected_cpm"]),
            }
        )
        remaining_capacity[sid] -= 1
        remaining_target[cid] -= impr
        campaign_impr[cid] += impr

    assignments = pd.DataFrame(rows)
    revenue = float(assignments["revenue"].sum()) if len(assignments) else 0.0
    delivered = float(assignments["impressions"].sum()) if len(assignments) else 0.0
    fill_rate = delivered / total_impressions if total_impressions else 0.0
    method = "greedy" if stop_at_target else "greedy_fair"
    return AllocationResult(assignments, revenue, fill_rate, method)
