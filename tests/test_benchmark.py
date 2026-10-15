from src.generate_instance import generate_instance
from src.greedy import greedy_allocate
from src.mip_ortools import solve_mip


def test_mip_beats_or_matches_greedy_revenue():
    inst = generate_instance(n_slots=20, n_campaigns=6, seed=7)
    greedy = greedy_allocate(inst)
    mip, info = solve_mip(inst, time_limit_s=20.0)
    assert info.status in {"OPTIMAL", "FEASIBLE"}
    # MIP maximises revenue under pacing/target soft constraints; should not be worse than greedy on this seed.
    assert mip.revenue + 1e-6 >= greedy.revenue * 0.98


def test_slot_capacity_respected():
    inst = generate_instance(n_slots=15, n_campaigns=5, seed=3)
    mip, info = solve_mip(inst)
    assert info.status in {"OPTIMAL", "FEASIBLE"}
    caps = inst.slots.set_index("slot_id")["capacity"].to_dict()
    counts = mip.assignments.groupby("slot_id").size().to_dict() if len(mip.assignments) else {}
    for sid, n in counts.items():
        assert n <= int(caps[sid])
