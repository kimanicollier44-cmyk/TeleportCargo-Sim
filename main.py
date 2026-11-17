#!/usr/bin/env python3
"""TeleportCargo-Sim - educational quantum teleportation cargo simulator.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
Education only - and the lesson is the honest core, stated up front:

  * Teleportation moves quantum STATE information only. It never
    moves matter, never moves mass, and never moves anything
    faster than light.
  * A "cargo job" in this lab = teleporting the quantum state of a
    payload register, qubit by qubit. Each qubit costs exactly one
    Bell pair (consumed) plus 2 classical bits, and those classical
    bits travel on an ordinary light-speed-limited channel. The
    teleportation is not complete - not even in principle - until
    the classical bits arrive, so no job in this lab ever beats
    light, and the latency budget charges full light time.
  * Rebuilding anything physical at the far end needs LOCAL matter
    at the far end plus the state information. Teleporting the
    state of macroscopic matter is not possible with known physics.

This lab does the resource accounting for such jobs with the family
physics verified in EntangleNet-Q / BellPair-Factory /
TeleportNet-Router: Werner pairs F = (1 + 3w)/4, DEJMPS
purification priced in raw pairs (2 / P_success per round),
entanglement swapping by the Werner-weight product rule, teleport
output fidelity (2F + 1)/3 judged against the 2/3 classical limit,
and memory decay w(t) = w0 * exp(-t / T2) while jobs wait in the
queue. Infeasible jobs are REFUSED with named reasons - never
waved through. Every matter / FTL / live-operation / commercial
cargo claim is a HOLD gate - with Gemini Carbon 4 as DECIDER
(names-only, tighten-only), Muse as advisor (never overrides
HOLD), and Google Flow plan-only seats.
"""
import hashlib
import json
import math
import sys

# ---------------------------------------------------------------- constants
C_LIGHT = 299792458.0           # speed of light, m/s (exact, SI)
C_FIBER_KM_S = 200_000.0        # light speed in fiber, km/s (family sim value)
VERSION = "1.0.0"

# Family physics constants (EntangleNet-Q / BellPair-Factory /
# TeleportNet-Router - same values, same formulas, verified there).
MEMORY_T2_S = 1.0               # memory coherence time, seconds (sim parameter)
MAX_PURIFY_ROUNDS = 6           # factory policy cap per delivered pair
CLASSICAL_LIMIT = 2.0 / 3.0     # best classical teleport fidelity
CLASSICAL_BITS_PER_QUBIT = 2    # Bell-measurement outcomes per teleported qubit
PAIRS_PER_QUBIT = 1             # one Bell pair consumed per teleported qubit

# The factory front-end: BellPair-Factory's spdc-line-a, the family
# workhorse - raw Werner pairs at F = 0.75, 1,200 pairs/s, 1.0 credit.
RAW_PAIR_FIDELITY = 0.75
PAIR_RATE_PER_S = 1200.0
PAIR_COST_CREDITS = 1.0

# Classifier policy: a feasible job whose raw-pair bill passes this
# line is labelled "costly" instead of "feasible".
COSTLY_PAIR_BILL = 50_000.0

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "matter_teleportation_claim": "HOLD - teleportation moves quantum state information only; no matter is ever transported",
    "mass_transport_claim": "HOLD - no mass moves in teleportation; the payload register's state moves, its atoms stay home",
    "ftl_claim": "HOLD - nothing here is faster than light; the mandatory classical channel is light-speed-limited",
    "instant_delivery_claim": "HOLD - no instant delivery: a teleport finishes no sooner than its classical bits arrive",
    "macroscopic_matter_claim": "HOLD - teleporting macroscopic matter is not possible with known physics",
    "human_teleportation_claim": "HOLD - no teleporting people; a state description is not a person and no person is a payload",
    "living_cargo_claim": "HOLD - no living cargo of any kind; this lab moves simulated qubit states only",
    "live_network_operation": "HOLD - no operating any real quantum or classical network, ever",
    "commercial_cargo_service_claim": "HOLD - no commercial cargo or teleportation service exists here; this is an educational simulator",
    "real_hardware_control": "HOLD - no control of any real pair source, repeater, or quantum hardware, ever",
    "live_experiment": "HOLD - no live experiment instructions; this lab computes, it does not operate",
    "guaranteed_delivery_claim": "HOLD - no guaranteed delivery or fidelity; every number here is a labelled simulation result",
    "medical_claim": "HOLD - no medical claims; simulated state transfer treats no condition",
    "weapons_application_claim": "HOLD - no weapons application guidance of any kind",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ 1. Family physics layer
# Inherited from EntangleNet-Q, where every formula below was
# verified against a from-scratch statevector / density-matrix
# simulator (swapping product rule to 1e-9, DEJMPS map and success
# probability to 1e-9, teleport circuit vs (2F + 1)/3 to 1e-9), and
# reused unchanged by BellPair-Factory and TeleportNet-Router.
# A pair is a Werner state: rho = w |phi+><phi+| + (1-w) I/4,
# fidelity F = (1 + 3w)/4.

def werner_w_from_fidelity(F):
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    return (4.0 * F - 1.0) / 3.0


def werner_fidelity_from_w(w):
    return (1.0 + 3.0 * w) / 4.0


def purify_fidelity(F):
    """Fidelity after one successful DEJMPS round on two Werner pairs."""
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    third = (1.0 - F) / 3.0
    num = F * F + third * third
    den = F * F + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * third * third
    return num / den


def purify_success_prob(F):
    """Probability the two measurement outcomes agree (pair is kept)."""
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    third = (1.0 - F) / 3.0
    return F * F + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * third * third


def purify_rounds(F, rounds):
    """Fidelity after `rounds` successful purification rounds."""
    for _ in range(rounds):
        F = purify_fidelity(F)
    return F


def chain_w(weights):
    """End-to-end Werner weight of a swapped chain: product of weights."""
    w = 1.0
    for x in weights:
        w *= x
    return w


def chain_fidelity(fidelities):
    """End-to-end fidelity of a chain of Werner pairs (product rule)."""
    return werner_fidelity_from_w(chain_w([werner_w_from_fidelity(f)
                                           for f in fidelities]))


def teleport_fidelity_from_pair(F):
    """Average teleportation fidelity using a Werner pair of fidelity F."""
    return (2.0 * F + 1.0) / 3.0


def decayed_fidelity(F, wait_s, t2=MEMORY_T2_S):
    """Fidelity of a Werner pair after waiting `wait_s` in memory.

    The Werner weight decays: w(t) = w0 * exp(-t / T2). A pair that
    waits long enough decays toward the maximally mixed floor
    F = 0.25 - inventory on the shelf is inventory going bad.
    """
    if wait_s < 0:
        raise ValueError("wait time must be non-negative")
    return werner_fidelity_from_w(werner_w_from_fidelity(F)
                                  * math.exp(-wait_s / t2))


# ================================================================ 2. Purification economics
# DEJMPS is not free fidelity. One round consumes two pairs and
# keeps one only when the measurement outcomes agree, so the
# expected raw pairs behind one delivered pair multiply by
# 2 / P_success(F) at the fidelity entering EVERY round. Fidelity
# climbs; the pair bill compounds. (BellPair-Factory's central
# economic fact, priced here for the cargo factory's SPDC line:
# raw F = 0.75 purifies to F = 0.9446 in 6 rounds, bill 224 pairs.)

def pairs_expected(F0, rounds):
    """Expected raw pairs consumed to deliver one purified pair."""
    pairs = 1.0
    F = F0
    for _ in range(rounds):
        pairs *= 2.0 / purify_success_prob(F)
        F = purify_fidelity(F)
    return pairs


def rounds_to_target(F0, target_F, max_rounds=MAX_PURIFY_ROUNDS):
    """Smallest round count reaching `target_F`, or (None, best F).

    Returns (rounds, fidelity_after). DEJMPS only helps above
    F = 0.5 and converges slowly, so some targets are honestly
    unreachable inside the factory's round cap.
    """
    F = F0
    if F >= target_F:
        return 0, F
    for r in range(1, max_rounds + 1):
        F = purify_fidelity(F)
        if F >= target_F:
            return r, F
    return None, F


def purification_table(max_rounds=MAX_PURIFY_ROUNDS):
    """Round-by-round economics for the cargo factory's SPDC line."""
    rows = []
    F = RAW_PAIR_FIDELITY
    for r in range(max_rounds + 1):
        pe = pairs_expected(RAW_PAIR_FIDELITY, r)
        rows.append({
            "rounds": r,
            "fidelity": round(F, 6),
            "pairs_expected": round(pe, 4),
            "output_rate_per_s": round(PAIR_RATE_PER_S / pe, 4),
            "cost_per_delivered": round(PAIR_COST_CREDITS * pe, 4),
            "teleport_fidelity": round(teleport_fidelity_from_pair(F), 6),
        })
        F = purify_fidelity(F)
    return rows


# ================================================================ 3. Latency budget
# Teleportation is finished only when the receiver gets the 2
# classical bits per qubit and applies the correction. Those bits
# ride an ordinary channel at (at best) light speed, so the
# end-to-end latency of ANY teleport is bounded below by the
# one-way light time of the route. The budget below charges it in
# full - fibre at the family value C_FIBER_KM_S, vacuum at c.
# Distances are labelled approximate route distances.

ROUTES_KM = {
    "porter-ranch-to-los-angeles": 45.0,
    "porter-ranch-to-leo-orbit": 550.0,
    "los-angeles-to-san-francisco": 559.0,
    "los-angeles-to-new-york": 3974.0,
    "earth-to-moon": 384400.0,
}


def light_time_s(distance_km, medium="fiber"):
    """One-way light time of the classical channel over distance_km."""
    if distance_km < 0:
        raise ValueError("distance must be non-negative")
    if medium == "fiber":
        return distance_km / C_FIBER_KM_S
    if medium == "vacuum":
        return distance_km * 1000.0 / C_LIGHT
    raise ValueError("medium must be 'fiber' or 'vacuum'")


def latency_report():
    """Light-time floor for every labelled route, both media."""
    out = {}
    for name, km in ROUTES_KM.items():
        out[name] = {
            "distance_km": km,
            "fiber_s": round(light_time_s(km, "fiber"), 6),
            "vacuum_s": round(light_time_s(km, "vacuum"), 6),
            "teleport_faster_than_light": False,
        }
    return out


# ================================================================ 4. Job accounting
# A cargo job teleports the state of a `qubits`-qubit payload
# register across `hops` relay links. Per qubit: PAIRS_PER_QUBIT
# end-to-end pair, and each end-to-end pair is a swapped chain of
# `hops` link pairs. Every link pair starts raw at
# RAW_PAIR_FIDELITY and is purified to the job's target fidelity -
# the pair bill therefore compounds per link pair. Classical cost:
# CLASSICAL_BITS_PER_QUBIT bits per qubit, full stop, and the job
# cannot complete before those bits cross the route at light speed.

def account_job(job):
    """Full resource accounting for one cargo job (dict in, dict out).

    Required job fields: name, qubits, hops, target_fidelity,
    distance_km. Feasibility here is physics only: purification
    target reachable inside the round cap, and the end-to-end
    teleport fidelity beating the 2/3 classical limit.
    """
    qubits = int(job["qubits"])
    hops = int(job["hops"])
    target = float(job["target_fidelity"])
    distance = float(job["distance_km"])
    reasons = []
    if qubits <= 0:
        reasons.append("EMPTY_PAYLOAD")
    if hops <= 0:
        reasons.append("NO_ROUTE")
    rounds, pair_f = rounds_to_target(RAW_PAIR_FIDELITY, target)
    if rounds is None:
        reasons.append("TARGET_FIDELITY_UNREACHABLE")
        pair_f = purify_rounds(RAW_PAIR_FIDELITY, MAX_PURIFY_ROUNDS)
        bill = pairs_expected(RAW_PAIR_FIDELITY, MAX_PURIFY_ROUNDS)
        rounds_used = MAX_PURIFY_ROUNDS
    else:
        bill = pairs_expected(RAW_PAIR_FIDELITY, rounds)
        rounds_used = rounds
    link_pairs = qubits * hops * PAIRS_PER_QUBIT
    raw_pairs = link_pairs * bill
    chain_f = chain_fidelity([pair_f] * hops) if hops > 0 else 0.25
    tele_f = teleport_fidelity_from_pair(chain_f)
    if tele_f <= CLASSICAL_LIMIT:
        reasons.append("CLASSICAL_LIMIT_FAIL")
    transit = light_time_s(distance, "fiber")
    production = raw_pairs / PAIR_RATE_PER_S
    return {
        "name": job["name"],
        "qubits": qubits,
        "hops": hops,
        "target_fidelity": target,
        "distance_km": distance,
        "purify_rounds": rounds,
        "pair_fidelity": round(pair_f, 6),
        "pairs_per_link_pair": round(bill, 4),
        "link_pairs": link_pairs,
        "raw_pairs_total": round(raw_pairs, 2),
        "cost_credits": round(raw_pairs * PAIR_COST_CREDITS, 2),
        "classical_bits": CLASSICAL_BITS_PER_QUBIT * qubits,
        "chain_fidelity": round(chain_f, 6),
        "teleport_fidelity": round(tele_f, 6),
        "classical_limit": round(CLASSICAL_LIMIT, 6),
        "beats_classical": tele_f > CLASSICAL_LIMIT,
        "light_time_s": round(transit, 6),
        "production_s": round(production, 4),
        "min_latency_s": round(production + transit, 4),
        "feasible": not reasons,
        "reasons": reasons,
        "_rounds_used": rounds_used,
    }


# ================================================================ 5. Manifest checker
# The interlock desk. Physics feasibility (section 4) plus the
# paperwork checks a real manifest would face: the declared qubit
# count must match the measured register, the job must fit its
# latency allowance, and the raw-pair budget must cover the bill.
# Any failure REFUSES the job with named reasons - no warnings
# dressed up as approvals.

def validate_job(job, pair_budget=None):
    """Manifest verdict for one job: accepted flag + named reasons."""
    acct = account_job(job)
    reasons = list(acct["reasons"])
    declared = job.get("declared_qubits", job["qubits"])
    if int(declared) != int(job["qubits"]):
        reasons.append("QUBIT_COUNT_MISMATCH")
    max_latency = job.get("max_latency_s")
    if max_latency is not None and acct["min_latency_s"] > float(max_latency):
        reasons.append("LATENCY_EXCEEDED")
    if pair_budget is not None and acct["raw_pairs_total"] > float(pair_budget):
        reasons.append("PAIR_BUDGET_EXCEEDED")
    return {"name": job["name"], "accepted": not reasons, "reasons": reasons,
            "accounting": acct}


# The worked example book. Three teaching jobs plus one paperwork
# failure: an easy sensor state, a heavy register with a heavy
# bill, a hop-heavy job whose swapped chain collapses below the
# classical limit (REFUSED), and a misdeclared manifest (REFUSED).
JOB_BOOK = [
    {"name": "sensor-state-10q", "qubits": 10, "declared_qubits": 10,
     "hops": 1, "target_fidelity": 0.90, "distance_km": 45.0,
     "max_latency_s": 60.0, "arrival_s": 0.5},
    {"name": "register-1000q", "qubits": 1000, "declared_qubits": 1000,
     "hops": 2, "target_fidelity": 0.90, "distance_km": 559.0,
     "max_latency_s": 3600.0, "arrival_s": 0.0},
    {"name": "hop-heavy-5q", "qubits": 5, "declared_qubits": 5,
     "hops": 12, "target_fidelity": 0.75, "distance_km": 2400.0,
     "max_latency_s": 3600.0, "arrival_s": 1.0},
    {"name": "misdeclared-20q", "qubits": 20, "declared_qubits": 18,
     "hops": 1, "target_fidelity": 0.90, "distance_km": 45.0,
     "max_latency_s": 60.0, "arrival_s": 2.0},
]


def job_book_report(pair_budget=None):
    return {j["name"]: validate_job(j, pair_budget=pair_budget)
            for j in JOB_BOOK}


# ================================================================ 6. Job scheduler
# One factory line, deterministic FIFO: jobs are served in
# (arrival_s, name) order and the line produces raw pairs at
# PAIR_RATE_PER_S, so a job's production window is its raw-pair
# bill divided by the rate. While a job WAITS in the queue, the
# link pairs staged for it sit in memory and decay with the family
# T2 model - with T2 = 1.0 s, a long wait is not an inconvenience,
# it is a fidelity collapse, and a job whose post-wait teleport
# fidelity falls to the classical limit is REFUSED at the dock.
# (Model boundary, stated honestly: pairs are consumed as produced
# inside a job's own production window, pipelined; only the queue
# wait before production is charged as decay.)

def simulate_schedule(jobs=None):
    """Deterministic FIFO schedule with queue-decay refusals."""
    if jobs is None:
        jobs = [j for j in JOB_BOOK if j["name"] != "misdeclared-20q"]
    ordered = sorted(jobs, key=lambda j: (float(j.get("arrival_s", 0.0)),
                                          j["name"]))
    factory_free = 0.0
    out = []
    for job in ordered:
        acct = account_job(job)
        arrival = float(job.get("arrival_s", 0.0))
        row = {"name": job["name"], "arrival_s": round(arrival, 4)}
        if not acct["feasible"]:
            row.update({"status": "REFUSED", "reasons": acct["reasons"],
                        "wait_s": 0.0, "start_s": None, "finish_s": None,
                        "teleport_fidelity": acct["teleport_fidelity"]})
            out.append(row)
            continue
        start = max(arrival, factory_free)
        wait = start - arrival
        finish = start + acct["production_s"]
        factory_free = finish
        pair_f_waited = decayed_fidelity(acct["pair_fidelity"], wait)
        chain_f = chain_fidelity([pair_f_waited] * acct["hops"])
        tele_f = teleport_fidelity_from_pair(chain_f)
        row.update({
            "wait_s": round(wait, 4),
            "start_s": round(start, 4),
            "finish_s": round(finish, 4),
            "pair_fidelity_after_wait": round(pair_f_waited, 6),
            "teleport_fidelity": round(tele_f, 6),
        })
        if tele_f <= CLASSICAL_LIMIT:
            row.update({"status": "REFUSED",
                        "reasons": ["QUEUE_DECAY_BELOW_CLASSICAL"]})
        else:
            row.update({"status": "DELIVERED", "reasons": []})
        out.append(row)
    return out


# ================================================================ 7. kNN regime classifier
# Features: (log10 qubits, hops / 5, target fidelity x 2). The
# labels come from the accounting model itself (section 4 + the
# COSTLY_PAIR_BILL policy line): a job the model refuses is
# "infeasible", a feasible job with a five-figure-plus raw-pair
# bill is "costly", everything else the model accepts cheaply is
# "feasible". Training rows are labelled by that same rule.

def model_label(qubits, hops, target_fidelity):
    """Ground-truth regime label from the accounting model."""
    acct = account_job({"name": "probe", "qubits": qubits, "hops": hops,
                        "target_fidelity": target_fidelity,
                        "distance_km": 0.0})
    if not acct["feasible"]:
        return "infeasible"
    if acct["raw_pairs_total"] > COSTLY_PAIR_BILL:
        return "costly"
    return "feasible"


_CLASSIFIER_TRAIN = [
    # (log10_qubits, hops/5, target_F x2, label)
    (0.30, 0.2, 1.70, "feasible"),    # 2 q, 1 hop, F 0.85
    (1.00, 0.2, 1.80, "feasible"),    # 10 q, 1 hop, F 0.90
    (1.30, 0.2, 1.80, "feasible"),    # 20 q, 1 hop, F 0.90
    (1.00, 0.4, 1.80, "feasible"),    # 10 q, 2 hops, F 0.90
    (2.00, 0.2, 1.70, "feasible"),    # 100 q, 1 hop, F 0.85
    (0.70, 0.6, 1.80, "feasible"),    # 5 q, 3 hops, F 0.90
    (3.00, 0.4, 1.80, "costly"),      # 1000 q, 2 hops, F 0.90
    (4.00, 0.6, 1.80, "costly"),      # 10000 q, 3 hops, F 0.90
    (3.00, 0.2, 1.80, "costly"),      # 1000 q, 1 hop, F 0.90
    (2.70, 0.4, 1.88, "costly"),      # 500 q, 2 hops, F 0.94 target
    (4.00, 0.2, 1.70, "costly"),      # 10000 q, 1 hop, F 0.85
    (3.30, 0.6, 1.70, "costly"),      # 2000 q, 3 hops, F 0.85
    (0.70, 2.4, 1.50, "infeasible"),  # 5 q, 12 hops, F 0.75
    (1.30, 4.0, 1.60, "infeasible"),  # 20 q, 20 hops, F 0.80
    (1.00, 2.0, 1.60, "infeasible"),  # 10 q, 10 hops, F 0.80
    (2.00, 1.6, 1.70, "infeasible"),  # 100 q, 8 hops, F 0.85
    (0.30, 3.0, 1.50, "infeasible"),  # 2 q, 15 hops, F 0.75
    (1.70, 2.4, 1.80, "infeasible"),  # 50 q, 12 hops, F 0.90
]


def _features(qubits, hops, target_fidelity):
    return (math.log10(qubits), hops / 5.0, target_fidelity * 2.0)


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def classify_regime(qubits, hops, target_fidelity, k=3):
    """kNN (k=3) cargo-job regime classifier on physical features."""
    if qubits <= 0 or hops <= 0:
        raise ValueError("qubits and hops must be positive")
    if not 0.25 < target_fidelity <= 1.0:
        raise ValueError("target fidelity must be in (0.25, 1]")
    f = _features(qubits, hops, target_fidelity)
    ranked = sorted(_CLASSIFIER_TRAIN, key=lambda row: _dist(f, row[:3]))
    votes = {}
    for row in ranked[:k]:
        votes[row[3]] = votes.get(row[3], 0) + 1
    return max(sorted(votes), key=lambda lab: votes[lab])


def regime_report():
    scenarios = {
        "sensor_10q_1hop_090": (10, 1, 0.90),
        "register_1000q_2hop_090": (1000, 2, 0.90),
        "hopheavy_5q_12hop_075": (5, 12, 0.75),
        "small_2q_1hop_085": (2, 1, 0.85),
        "bulk_10000q_3hop_090": (10000, 3, 0.90),
        "deepchain_20q_20hop_080": (20, 20, 0.80),
    }
    return {name: classify_regime(q, h, t)
            for name, (q, h, t) in scenarios.items()}


# ================================================================ 8. Advisory seats
def _trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="teleportcargo-sim-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all claim gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="teleportcargo-sim-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Say it in the first line of every report: teleportation moves state information, never matter, never faster than light - then price the pairs, charge the full light time, and refuse any job whose chain falls to the classical limit.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["a payload register drawn as light, its atoms staying home",
                  "Bell pairs spent one per qubit, two classical bits riding a fibre",
                  "a swapped chain dimming hop by hop toward the classical limit",
                  "the queue where waiting pairs decay toward the mixed floor",
                  "the manifest desk stamping REFUSED on the hop-heavy job"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # 1. family physics layer
    chk("werner_roundtrip",
        abs(werner_w_from_fidelity(werner_fidelity_from_w(0.6)) - 0.6) < 1e-12)
    chk("werner_w_at_raw_fidelity",
        abs(werner_w_from_fidelity(RAW_PAIR_FIDELITY) - 2.0 / 3.0) < 1e-12)
    chk("purify_improves_fidelity", purify_fidelity(0.75) > 0.75)
    chk("purify_six_rounds_family_value",
        abs(purify_rounds(0.75, 6) - 0.9446) < 1e-3)
    chk("purify_success_prob_raw",
        abs(purify_success_prob(0.75) - 0.722222) < 1e-5)
    chk("pairs_expected_zero_rounds", pairs_expected(0.75, 0) == 1.0)
    chk("pairs_expected_six_rounds_family",
        abs(pairs_expected(0.75, 6) - 224.0) < 2.0)
    r90, _ = rounds_to_target(0.75, 0.90)
    chk("rounds_to_090_is_five", r90 == 5)
    r999, _ = rounds_to_target(0.75, 0.999)
    chk("rounds_to_0999_unreachable", r999 is None)
    chk("chain_product_rule",
        abs(chain_fidelity([0.75, 0.75]) - (1.0 + 3.0 * (4.0 / 9.0)) / 4.0) < 1e-12)
    chk("chain_single_link_identity", abs(chain_fidelity([0.9]) - 0.9) < 1e-12)
    chk("teleport_formula_raw",
        abs(teleport_fidelity_from_pair(0.75) - 2.5 / 3.0) < 1e-12)
    chk("teleport_perfect_pair", teleport_fidelity_from_pair(1.0) == 1.0)
    chk("teleport_classical_boundary",
        abs(teleport_fidelity_from_pair(0.5) - CLASSICAL_LIMIT) < 1e-12)
    chk("decay_zero_wait_identity", decayed_fidelity(0.85, 0.0) == 0.85)
    chk("decay_reduces_fidelity",
        decayed_fidelity(0.85, 0.5) < 0.85
        and decayed_fidelity(0.85, 0.1) > decayed_fidelity(0.85, 0.5))
    chk("decay_long_wait_floor", abs(decayed_fidelity(0.9, 50.0) - 0.25) < 1e-6)
    # 2. job accounting - the worked examples
    book = {j["name"]: j for j in JOB_BOOK}
    sensor = account_job(book["sensor-state-10q"])
    chk("sensor_link_pairs", sensor["link_pairs"] == 10)
    chk("sensor_classical_bits", sensor["classical_bits"] == 20)
    chk("sensor_raw_pairs_bill",
        abs(sensor["raw_pairs_total"] - 10 * pairs_expected(0.75, 5)) < 0.01)
    chk("sensor_feasible", sensor["feasible"] and sensor["reasons"] == [])
    chk("sensor_beats_classical", sensor["beats_classical"]
        and sensor["teleport_fidelity"] > CLASSICAL_LIMIT)
    register = account_job(book["register-1000q"])
    chk("register_classical_bits", register["classical_bits"] == 2000)
    chk("register_raw_pairs_heavy", register["raw_pairs_total"] > 100_000)
    chk("register_feasible", register["feasible"] and register["beats_classical"])
    hopheavy = account_job(book["hop-heavy-5q"])
    chk("hopheavy_classical_limit_fail",
        not hopheavy["feasible"]
        and "CLASSICAL_LIMIT_FAIL" in hopheavy["reasons"])
    chk("hopheavy_teleport_value",
        abs(hopheavy["teleport_fidelity"] - 0.5039) < 0.002)
    chk("hopheavy_zero_rounds", hopheavy["purify_rounds"] == 0
        and hopheavy["pairs_per_link_pair"] == 1.0)
    unreachable = account_job({"name": "probe", "qubits": 4, "hops": 1,
                               "target_fidelity": 0.999, "distance_km": 10.0})
    chk("unreachable_target_refused",
        "TARGET_FIDELITY_UNREACHABLE" in unreachable["reasons"])
    # 3. latency budget - light speed is a floor, never a target beaten
    chk("fiber_la_sf_exact", abs(light_time_s(559.0, "fiber") - 0.002795) < 1e-9)
    chk("vacuum_moon_value", abs(light_time_s(384400.0, "vacuum") - 1.2822) < 0.001)
    chk("fiber_slower_than_vacuum",
        light_time_s(559.0, "fiber") > light_time_s(559.0, "vacuum"))
    chk("teleport_never_beats_light",
        sensor["min_latency_s"] >= sensor["light_time_s"])
    lat = latency_report()
    chk("latency_report_no_ftl",
        all(row["teleport_faster_than_light"] is False for row in lat.values()))
    # 4. manifest checker interlocks
    chk("manifest_sensor_accepted",
        validate_job(book["sensor-state-10q"])["accepted"])
    mism = validate_job(book["misdeclared-20q"])
    chk("manifest_mismatch_refused",
        not mism["accepted"] and "QUBIT_COUNT_MISMATCH" in mism["reasons"])
    slow = dict(book["sensor-state-10q"], max_latency_s=0.1)
    chk("manifest_latency_refused",
        "LATENCY_EXCEEDED" in validate_job(slow)["reasons"])
    broke = validate_job(book["register-1000q"], pair_budget=1000)
    chk("manifest_budget_refused",
        "PAIR_BUDGET_EXCEEDED" in broke["reasons"])
    # 5. scheduler - FIFO, decay refusals, determinism of order
    sched = simulate_schedule()
    by_name = {row["name"]: row for row in sched}
    chk("schedule_fifo_first_is_register", sched[0]["name"] == "register-1000q")
    chk("schedule_register_delivered",
        by_name["register-1000q"]["status"] == "DELIVERED"
        and by_name["register-1000q"]["wait_s"] == 0.0)
    chk("schedule_sensor_decay_refused",
        by_name["sensor-state-10q"]["status"] == "REFUSED"
        and "QUEUE_DECAY_BELOW_CLASSICAL" in by_name["sensor-state-10q"]["reasons"]
        and by_name["sensor-state-10q"]["wait_s"] > 10.0)
    chk("schedule_hopheavy_refused",
        by_name["hop-heavy-5q"]["status"] == "REFUSED"
        and "CLASSICAL_LIMIT_FAIL" in by_name["hop-heavy-5q"]["reasons"])
    chk("schedule_sensor_alone_delivers",
        simulate_schedule([book["sensor-state-10q"]])[0]["status"] == "DELIVERED")
    # 6. classifier - agrees with the accounting model on every scenario
    rep = regime_report()
    chk("classifier_sensor_feasible", rep["sensor_10q_1hop_090"] == "feasible")
    chk("classifier_register_costly", rep["register_1000q_2hop_090"] == "costly")
    chk("classifier_hopheavy_infeasible", rep["hopheavy_5q_12hop_075"] == "infeasible")
    chk("classifier_small_feasible", rep["small_2q_1hop_085"] == "feasible")
    chk("classifier_bulk_costly", rep["bulk_10000q_3hop_090"] == "costly")
    chk("classifier_deepchain_infeasible",
        rep["deepchain_20q_20hop_080"] == "infeasible")
    chk("classifier_matches_model",
        all(classify_regime(q, h, t) == model_label(q, h, t)
            for (q, h, t) in [(10, 1, 0.90), (1000, 2, 0.90), (5, 12, 0.75),
                              (2, 1, 0.85), (10000, 3, 0.90), (20, 20, 0.80)]))
    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14
        and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_matter_hold", gate("matter_teleportation_claim") == "HOLD")
    chk("gate_ftl_hold", gate("ftl_claim") == "HOLD")
    chk("gate_macroscopic_hold", gate("macroscopic_matter_claim") == "HOLD")
    chk("gate_commercial_hold", gate("commercial_cargo_service_claim") == "HOLD")
    chk("gate_live_network_hold", gate("live_network_operation") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("TeleportCargo-Sim - quantum teleportation cargo simulator")
    print("by Darion Kellar | MIT | pure stdlib | zero network | EDUCATION ONLY")
    print("=" * 68)
    print("\n[1] THE HONEST CORE - what teleportation is and is not")
    print("    Teleportation moves quantum STATE information only.")
    print("    It never moves matter. It never moves mass. It never beats light:")
    print(f"    every qubit costs {PAIRS_PER_QUBIT} Bell pair (consumed) + "
          f"{CLASSICAL_BITS_PER_QUBIT} classical bits, and the job is not")
    print("    done until those bits arrive over a light-speed-limited channel.")
    print("    Rebuilding anything physical needs LOCAL matter at the far end;")
    print("    macroscopic matter teleportation is not possible (HOLD gate).")
    print("\n[2] Factory line - SPDC pairs, DEJMPS purification economics")
    print(f"    raw pair F = {RAW_PAIR_FIDELITY} at {PAIR_RATE_PER_S:.0f} pairs/s "
          f"(BellPair-Factory spdc-line-a)")
    for row in purification_table():
        print(f"    rounds {row['rounds']}: F = {row['fidelity']:.4f} | "
              f"bill {row['pairs_expected']:8.2f} raw pairs | "
              f"out {row['output_rate_per_s']:8.2f} pairs/s | "
              f"teleport F = {row['teleport_fidelity']:.4f}")
    print("    -> fidelity climbs, the pair bill compounds: 6 rounds reach")
    print("       F = 0.9446 (the family's published value) at 224 raw pairs each.")
    print("\n[3] Worked cargo jobs - full resource accounting")
    for job in JOB_BOOK:
        a = account_job(job)
        print(f"    {a['name']:18s} {a['qubits']:5d} q x {a['hops']:2d} hops: "
              f"raw pairs {a['raw_pairs_total']:>12,.2f} | "
              f"bits {a['classical_bits']:5d} | "
              f"teleport F = {a['teleport_fidelity']:.4f} | "
              f"{'FEASIBLE' if a['feasible'] else 'REFUSED ' + ','.join(a['reasons'])}")
    print("    -> 1 pair + 2 bits per qubit, purification billed per link pair.")
    print("       The 1,000-qubit register is feasible and expensive; the")
    print("       12-hop job collapses below the 2/3 classical limit - REFUSED.")
    print("\n[4] Fidelity chain - swapping eats fidelity (Werner product rule)")
    sensor = account_job(JOB_BOOK[0])
    print(f"    sensor job: link F = {sensor['pair_fidelity']:.4f} after "
          f"{sensor['purify_rounds']} rounds, 1 hop -> teleport "
          f"F = {sensor['teleport_fidelity']:.4f} (classical limit 0.6667)")
    hopheavy = account_job(JOB_BOOK[2])
    print(f"    hop-heavy : raw link F = 0.7500, 12 hops -> chain "
          f"F = {hopheavy['chain_fidelity']:.4f} -> teleport "
          f"F = {hopheavy['teleport_fidelity']:.4f} < 0.6667 REFUSED")
    print("    -> Werner weights multiply per hop; long raw chains are worse")
    print("       than a classical send. Purify, shorten the chain, or refuse.")
    print("\n[5] Latency budget - the classical leg at light speed (one-way)")
    for name, row in latency_report().items():
        print(f"    {name:32s} {row['distance_km']:>9,.0f} km: "
              f"fiber {row['fiber_s']:.4f} s | vacuum {row['vacuum_s']:.4f} s")
    print("    -> no teleport completes before its classical bits arrive:")
    print("       LA -> SF can never beat 2.795 ms in fibre, the Moon 1.2822 s.")
    print("\n[6] Manifest checker - interlocks refuse bad paperwork")
    for name, verdict in job_book_report().items():
        print(f"    {name:18s} -> "
              f"{'ACCEPTED' if verdict['accepted'] else 'REFUSED ' + ','.join(verdict['reasons'])}")
    print("    -> declared vs measured qubits, latency allowance, pair budget:")
    print("       the misdeclared manifest (20 declared as 18) is refused.")
    print("\n[7] Scheduler - deterministic FIFO queue, pairs decay while waiting")
    for row in simulate_schedule():
        print(f"    {row['name']:18s} arrival {row['arrival_s']:5.1f} s | "
              f"wait {row['wait_s']:8.2f} s | {row['status']}"
              f"{' ' + ','.join(row['reasons']) if row['reasons'] else ''}")
    print(f"    -> memory T2 = {MEMORY_T2_S:.1f} s: the sensor job waits behind the")
    print("       register job, its staged pairs decay to the mixed floor, and")
    print("       it is REFUSED at the dock. A backlog is decaying inventory.")
    print("\n[8] Regime classifier (TinyML kNN, labels from the accounting model)")
    for name, label in regime_report().items():
        print(f"    {name:26s} -> {label}")
    print("\n[9] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[10] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "physics":
        print(json.dumps(purification_table(), indent=2, sort_keys=True))
        return 0
    if cmd == "account":
        print(json.dumps({j["name"]: account_job(j) for j in JOB_BOOK},
                         indent=2, sort_keys=True))
        return 0
    if cmd == "latency":
        print(json.dumps(latency_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "manifest":
        print(json.dumps(job_book_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "queue":
        print(json.dumps(simulate_schedule(), indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(regime_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "matter_teleportation_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
