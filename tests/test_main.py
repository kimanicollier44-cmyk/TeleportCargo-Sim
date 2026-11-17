"""Tests for TeleportCargo-Sim: every number checked against the family model."""
import math

import pytest

import main as m


BOOK = {j["name"]: j for j in m.JOB_BOOK}


# ---- family physics layer (EntangleNet-Q verified formulas)
def test_werner_roundtrip():
    assert abs(m.werner_w_from_fidelity(m.werner_fidelity_from_w(0.6)) - 0.6) < 1e-12


def test_werner_w_at_raw_fidelity():
    assert abs(m.werner_w_from_fidelity(0.75) - 2.0 / 3.0) < 1e-12


def test_werner_invalid_raises():
    with pytest.raises(ValueError):
        m.werner_w_from_fidelity(0.1)


def test_purify_improves_fidelity():
    assert m.purify_fidelity(0.75) > 0.75


def test_purify_six_rounds_family_value():
    # BellPair-Factory's published headline: 0.75 -> 0.9446 in 6 rounds
    assert abs(m.purify_rounds(0.75, 6) - 0.9446) < 1e-3


def test_purify_success_prob_raw():
    assert abs(m.purify_success_prob(0.75) - 0.722222) < 1e-5


def test_pairs_expected_zero_rounds():
    assert m.pairs_expected(0.75, 0) == 1.0


def test_pairs_expected_six_rounds_family_bill():
    # the family bill: ~224 raw pairs behind one 6-round delivered pair
    assert abs(m.pairs_expected(0.75, 6) - 224.0) < 2.0


def test_pairs_expected_grows_with_rounds():
    bills = [m.pairs_expected(0.75, r) for r in range(7)]
    assert all(bills[i] < bills[i + 1] for i in range(6))


def test_rounds_to_target_090():
    rounds, F = m.rounds_to_target(0.75, 0.90)
    assert rounds == 5 and F >= 0.90


def test_rounds_to_target_unreachable():
    rounds, F = m.rounds_to_target(0.75, 0.999)
    assert rounds is None and F < 0.999


def test_chain_product_rule():
    expected = (1.0 + 3.0 * (4.0 / 9.0)) / 4.0
    assert abs(m.chain_fidelity([0.75, 0.75]) - expected) < 1e-12


def test_chain_single_link_identity():
    assert abs(m.chain_fidelity([0.9]) - 0.9) < 1e-12


def test_chain_falls_with_hops():
    one = m.chain_fidelity([0.9])
    four = m.chain_fidelity([0.9] * 4)
    assert one > four > 0.25


def test_teleport_formula():
    assert abs(m.teleport_fidelity_from_pair(0.75) - 2.5 / 3.0) < 1e-12
    assert m.teleport_fidelity_from_pair(1.0) == 1.0


def test_teleport_classical_boundary():
    # a Werner pair at F = 0.5 teleports at exactly the classical limit
    assert abs(m.teleport_fidelity_from_pair(0.5) - 2.0 / 3.0) < 1e-12


def test_decay_zero_wait_identity():
    assert m.decayed_fidelity(0.85, 0.0) == 0.85


def test_decay_reduces_fidelity():
    assert m.decayed_fidelity(0.85, 0.5) < 0.85
    assert m.decayed_fidelity(0.85, 0.1) > m.decayed_fidelity(0.85, 0.5)


def test_decay_long_wait_floor():
    assert abs(m.decayed_fidelity(0.9, 50.0) - 0.25) < 1e-6


# ---- job accounting: the worked examples
def test_sensor_job_accounting():
    a = m.account_job(BOOK["sensor-state-10q"])
    assert a["link_pairs"] == 10
    assert a["classical_bits"] == 20
    assert a["purify_rounds"] == 5
    assert abs(a["raw_pairs_total"] - 1010.93) < 0.01
    assert a["feasible"] and a["beats_classical"]


def test_register_job_accounting():
    a = m.account_job(BOOK["register-1000q"])
    assert a["classical_bits"] == 2000
    assert a["raw_pairs_total"] > 100_000
    assert abs(a["teleport_fidelity"] - 0.9027) < 0.001
    assert a["feasible"]


def test_hopheavy_job_refused_classical_limit():
    a = m.account_job(BOOK["hop-heavy-5q"])
    assert not a["feasible"]
    assert "CLASSICAL_LIMIT_FAIL" in a["reasons"]
    assert abs(a["chain_fidelity"] - 0.2558) < 0.001
    assert abs(a["teleport_fidelity"] - 0.5039) < 0.002


def test_unreachable_target_refused():
    a = m.account_job({"name": "probe", "qubits": 4, "hops": 1,
                       "target_fidelity": 0.999, "distance_km": 10.0})
    assert "TARGET_FIDELITY_UNREACHABLE" in a["reasons"]


def test_accounting_scales_linearly_in_qubits():
    j1 = {"name": "a", "qubits": 10, "hops": 1,
          "target_fidelity": 0.90, "distance_km": 10.0}
    j2 = dict(j1, name="b", qubits=20)
    a1, a2 = m.account_job(j1), m.account_job(j2)
    assert abs(a2["raw_pairs_total"] - 2 * a1["raw_pairs_total"]) < 0.01
    assert a2["classical_bits"] == 2 * a1["classical_bits"]


# ---- latency budget: light speed is a floor
def test_fiber_la_sf_exact():
    assert abs(m.light_time_s(559.0, "fiber") - 0.002795) < 1e-9


def test_vacuum_moon_value():
    assert abs(m.light_time_s(384400.0, "vacuum") - 1.2822) < 0.001


def test_fiber_slower_than_vacuum():
    assert m.light_time_s(559.0, "fiber") > m.light_time_s(559.0, "vacuum")


def test_bad_medium_raises():
    with pytest.raises(ValueError):
        m.light_time_s(10.0, "warp")


def test_teleport_never_beats_light():
    for job in m.JOB_BOOK:
        a = m.account_job(job)
        assert a["min_latency_s"] >= a["light_time_s"]


def test_latency_report_no_ftl():
    rep = m.latency_report()
    assert all(row["teleport_faster_than_light"] is False for row in rep.values())


# ---- manifest checker interlocks
def test_manifest_sensor_accepted():
    v = m.validate_job(BOOK["sensor-state-10q"])
    assert v["accepted"] and v["reasons"] == []


def test_manifest_mismatch_refused():
    v = m.validate_job(BOOK["misdeclared-20q"])
    assert not v["accepted"]
    assert "QUBIT_COUNT_MISMATCH" in v["reasons"]


def test_manifest_latency_refused():
    job = dict(BOOK["sensor-state-10q"], max_latency_s=0.1)
    assert "LATENCY_EXCEEDED" in m.validate_job(job)["reasons"]


def test_manifest_budget_refused():
    v = m.validate_job(BOOK["register-1000q"], pair_budget=1000)
    assert "PAIR_BUDGET_EXCEEDED" in v["reasons"]


def test_manifest_budget_sufficient_accepts():
    v = m.validate_job(BOOK["register-1000q"], pair_budget=1_000_000)
    assert v["accepted"]


# ---- scheduler: FIFO + queue decay
def test_schedule_fifo_order_and_register_delivered():
    sched = m.simulate_schedule()
    assert sched[0]["name"] == "register-1000q"
    reg = sched[0]
    assert reg["status"] == "DELIVERED" and reg["wait_s"] == 0.0


def test_schedule_sensor_decay_refused():
    sched = {r["name"]: r for r in m.simulate_schedule()}
    s = sched["sensor-state-10q"]
    assert s["status"] == "REFUSED"
    assert "QUEUE_DECAY_BELOW_CLASSICAL" in s["reasons"]
    assert s["wait_s"] > 10.0
    assert s["pair_fidelity_after_wait"] == 0.25


def test_schedule_hopheavy_refused_at_manifest():
    sched = {r["name"]: r for r in m.simulate_schedule()}
    assert sched["hop-heavy-5q"]["status"] == "REFUSED"
    assert "CLASSICAL_LIMIT_FAIL" in sched["hop-heavy-5q"]["reasons"]


def test_schedule_sensor_alone_delivers():
    sched = m.simulate_schedule([BOOK["sensor-state-10q"]])
    assert sched[0]["status"] == "DELIVERED" and sched[0]["wait_s"] == 0.0


# ---- classifier agrees with the accounting model
def test_classifier_scenarios():
    rep = m.regime_report()
    assert rep["sensor_10q_1hop_090"] == "feasible"
    assert rep["register_1000q_2hop_090"] == "costly"
    assert rep["hopheavy_5q_12hop_075"] == "infeasible"
    assert rep["small_2q_1hop_085"] == "feasible"
    assert rep["bulk_10000q_3hop_090"] == "costly"
    assert rep["deepchain_20q_20hop_080"] == "infeasible"


def test_classifier_matches_model_on_scenarios():
    for (q, h, t) in [(10, 1, 0.90), (1000, 2, 0.90), (5, 12, 0.75),
                      (2, 1, 0.85), (10000, 3, 0.90), (20, 20, 0.80)]:
        assert m.classify_regime(q, h, t) == m.model_label(q, h, t)


def test_classifier_training_labels_match_model():
    for row in m._CLASSIFIER_TRAIN:
        q = round(10 ** row[0])
        h = round(row[1] * 5)
        t = row[2] / 2.0
        assert m.model_label(q, h, t) == row[3], (q, h, t, row[3])


# ---- gates + seats
def test_hold_gates_all_present():
    assert len(m.HOLD_GATES) == 14
    assert all(v.startswith("HOLD") for v in m.HOLD_GATES.values())


def test_claim_gates_hold():
    for action in ("matter_teleportation_claim", "mass_transport_claim",
                   "ftl_claim", "macroscopic_matter_claim",
                   "human_teleportation_claim",
                   "commercial_cargo_service_claim",
                   "live_network_operation"):
        assert m.gate(action) == "HOLD"


def test_sandbox_proceeds():
    assert m.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    b = m.brains_report()
    assert b["decider"]["can_override_hold"] is False
    assert b["advisor"]["can_override_hold"] is False
    assert b["flow"]["rendered"] is False and b["flow"]["live"] == 0


def test_demo_checks_all_pass():
    checks = m.run_checks()
    assert all(ok for _, ok in checks), [n for n, ok in checks if not ok]


def test_demo_deterministic():
    import io
    import contextlib
    out1, out2 = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out1):
        m.demo()
    with contextlib.redirect_stdout(out2):
        m.demo()
    assert out1.getvalue() == out2.getvalue()
