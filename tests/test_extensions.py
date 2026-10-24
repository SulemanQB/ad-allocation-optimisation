import pytest

from src.generate_instance import generate_instance
from src.greedy import greedy_allocate
from src.metrics import allocation_metrics
from src.mip_gurobi import gurobi_available, is_gurobi_licence_error, solve_mip_gurobi
from src.mip_ortools import solve_mip
from src.sensitivity import run_sensitivity, scale_capacity


def test_fair_greedy_uses_at_least_as_much_inventory():
    inst = generate_instance(n_slots=20, n_campaigns=6, seed=7)
    stop = allocation_metrics(inst, greedy_allocate(inst))
    fair = allocation_metrics(inst, greedy_allocate(inst, stop_at_target=False))
    assert fair["unsold_ad_units"] <= stop["unsold_ad_units"]
    assert fair["revenue"] >= stop["revenue"]


def test_revenue_only_mip_beats_fair_greedy():
    # With no shortfall penalty both methods chase pure revenue under the
    # same capacity/pacing limits, so the exact MIP can never do worse.
    inst = generate_instance(n_slots=20, n_campaigns=6, seed=7)
    mip, info = solve_mip(inst, time_limit_s=20.0, penalty=0.0)
    fair = greedy_allocate(inst, stop_at_target=False)
    assert info.status == "OPTIMAL"
    assert mip.revenue + 1e-6 >= fair.revenue


def test_hard_target_meets_all_targets_or_is_infeasible():
    inst = generate_instance(n_slots=20, n_campaigns=6, seed=7)
    res, info = solve_mip(inst, hard_target=True)
    if info.status in {"OPTIMAL", "FEASIBLE"}:
        assert allocation_metrics(inst, res)["pct_campaigns_at_target"] == 100.0
    else:
        assert info.status == "INFEASIBLE"


def test_capacity_scaling_changes_total():
    inst = generate_instance()
    total = int(inst.slots["capacity"].sum())
    assert int(scale_capacity(inst, 1.10).slots["capacity"].sum()) == round(1.10 * total)
    assert int(scale_capacity(inst, 0.90).slots["capacity"].sum()) == round(0.90 * total)
    assert (scale_capacity(inst, 0.90).slots["capacity"] >= 0).all()


def test_sensitivity_monotone_in_capacity():
    inst = generate_instance(n_slots=15, n_campaigns=5, seed=3)
    df = run_sensitivity(inst, time_limit_s=20.0)
    cap = df[df["sweep"] == "slot_capacity"].sort_values("factor")
    assert (cap["objective"].diff().dropna() >= -1e-6).all()


def test_gurobi_licence_errors_are_recognised():
    gurobipy = pytest.importorskip("gurobipy")
    from gurobipy import GRB

    assert is_gurobi_licence_error(
        gurobipy.GurobiError(GRB.ERROR_NO_LICENSE, "No Gurobi license found")
    )
    assert is_gurobi_licence_error(
        gurobipy.GurobiError(
            GRB.ERROR_SIZE_LIMIT_EXCEEDED,
            "Model too large for size-limited license",
        )
    )
    assert not is_gurobi_licence_error(
        gurobipy.GurobiError(GRB.ERROR_NUMERIC, "Numeric error encountered")
    )
    assert not is_gurobi_licence_error(RuntimeError("No Gurobi license found"))


def test_gurobi_unavailable_when_licence_file_is_missing(monkeypatch, tmp_path):
    pytest.importorskip("gurobipy")
    monkeypatch.setenv("GRB_LICENSE_FILE", str(tmp_path / "missing.lic"))
    assert gurobi_available() is False


@pytest.mark.skipif(not gurobi_available(), reason="Gurobi licence unavailable")
def test_gurobi_matches_cbc_objective():
    inst = generate_instance()
    _, cbc = solve_mip(inst)
    try:
        _, grb = solve_mip_gurobi(inst)
    except Exception as exc:
        if is_gurobi_licence_error(exc):
            pytest.skip("Gurobi licence unavailable")
        raise
    assert grb.status == "OPTIMAL"
    assert grb.objective == pytest.approx(cbc.objective, rel=1e-3)
