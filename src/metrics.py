"""Common reporting metrics for any allocation."""

from __future__ import annotations

from .generate_instance import Instance
from .greedy import AllocationResult


def allocation_metrics(instance: Instance, result: AllocationResult) -> dict:
    caps = instance.slots.set_index("slot_id")["capacity"].astype(int)
    targets = instance.campaigns.set_index("campaign_id")["target_impressions"].astype(float)
    a = result.assignments
    if len(a):
        used = a.groupby("slot_id").size().reindex(caps.index, fill_value=0)
        delivered = a.groupby("campaign_id")["impressions"].sum().reindex(targets.index, fill_value=0.0)
    else:
        used = caps * 0
        delivered = targets * 0.0
    at_target = int((delivered >= targets - 1e-6).sum())
    unsold_units = int((caps - used).clip(lower=0).sum())
    return {
        "method": result.method,
        "revenue": round(result.revenue, 2),
        "campaigns_at_target": at_target,
        "pct_campaigns_at_target": round(100.0 * at_target / len(targets), 1),
        "unsold_ad_units": unsold_units,
        "total_ad_units": int(caps.sum()),
        "unsold_pct": round(100.0 * unsold_units / int(caps.sum()), 1),
        "assignments": int(len(a)),
    }
