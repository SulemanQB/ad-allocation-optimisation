"""Synthetic ad-inventory instance for a media allocation MIP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Instance:
    slots: pd.DataFrame
    campaigns: pd.DataFrame
    rates: pd.DataFrame


def generate_instance(
    n_slots: int = 40,
    n_campaigns: int = 12,
    seed: int = 42,
) -> Instance:
    rng = np.random.default_rng(seed)
    channels = np.array(["broadcast_tv", "bvod", "svod_ad", "publishing", "outdoor"])
    dayparts = np.array(["breakfast", "daytime", "prime", "late"])

    slots = pd.DataFrame(
        {
            "slot_id": [f"S{i:03d}" for i in range(n_slots)],
            "channel": rng.choice(channels, size=n_slots),
            "daypart": rng.choice(dayparts, size=n_slots),
            "impressions": rng.integers(8_000, 120_000, size=n_slots),
            "capacity": rng.integers(1, 4, size=n_slots),
        }
    )

    campaigns = pd.DataFrame(
        {
            "campaign_id": [f"C{i:03d}" for i in range(n_campaigns)],
            "target_impressions": rng.integers(80_000, 450_000, size=n_campaigns),
            "max_cpm": rng.uniform(8.0, 45.0, size=n_campaigns).round(2),
            "priority": rng.integers(1, 4, size=n_campaigns),
            "pacing_max_share": rng.uniform(0.15, 0.45, size=n_campaigns).round(2),
        }
    )

    rows = []
    for _, slot in slots.iterrows():
        for _, camp in campaigns.iterrows():
            fit = 0.55 + 0.45 * rng.random()
            if slot["daypart"] == "prime":
                fit = min(1.0, fit + 0.1)
            cpm = float(camp["max_cpm"] * (0.7 + 0.5 * rng.random()))
            rows.append(
                {
                    "slot_id": slot["slot_id"],
                    "campaign_id": camp["campaign_id"],
                    "eligible": int(fit > 0.62),
                    "expected_cpm": round(cpm, 2),
                    "fit": round(fit, 3),
                }
            )
    rates = pd.DataFrame(rows)
    return Instance(slots=slots, campaigns=campaigns, rates=rates)


def write_instance(instance: Instance, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    instance.slots.to_csv(out_dir / "slots.csv", index=False)
    instance.campaigns.to_csv(out_dir / "campaigns.csv", index=False)
    instance.rates.to_csv(out_dir / "rates.csv", index=False)


def load_instance(data_dir: Path) -> Instance:
    return Instance(
        slots=pd.read_csv(data_dir / "slots.csv"),
        campaigns=pd.read_csv(data_dir / "campaigns.csv"),
        rates=pd.read_csv(data_dir / "rates.csv"),
    )


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    inst = generate_instance()
    write_instance(inst, root / "data")
    print(f"Wrote {len(inst.slots)} slots, {len(inst.campaigns)} campaigns to data/")
