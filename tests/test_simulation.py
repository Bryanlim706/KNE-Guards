from __future__ import annotations

from kne_guards.models import Action, MechanismScores, ProductSpec
from kne_guards.personas import generate_personas
from kne_guards.simulation import run_simulation
from kne_guards.tracking import build_report


def _mech_spec(**kwargs) -> ProductSpec:
    defaults = {"R": 0.7, "U": 0.7, "W": 0.7, "F": 0.5, "M": 0.4}
    defaults.update(kwargs)
    return ProductSpec(
        name="MechTest",
        category="study",
        features=["a", "b"],
        price_monthly=8.0,
        target_segment="students",
        substitutes=["alt1"],
        mechanisms=MechanismScores(**defaults),
    )


def _spec() -> ProductSpec:
    return ProductSpec(
        name="Test",
        category="study",
        features=["a", "b"],
        price_monthly=8.0,
        target_segment="students",
        substitutes=["alt1"],
    )


def test_simulation_is_deterministic():
    personas = generate_personas(50, seed=7)
    r1 = build_report(run_simulation(_spec(), personas, days=30, seed=7))
    r2 = build_report(run_simulation(_spec(), personas, days=30, seed=7))
    assert r1.retention_curve == r2.retention_curve
    assert r1.viability_score == r2.viability_score


def test_every_persona_has_one_event_per_day():
    personas = generate_personas(30, seed=1)
    result = run_simulation(_spec(), personas, days=30, seed=1)
    assert len(result.events) == 30 * (30 + 1)


def test_viability_score_in_range():
    personas = generate_personas(50, seed=1)
    report = build_report(run_simulation(_spec(), personas, days=30, seed=1))
    assert 0.0 <= report.viability_score <= 1.0


def test_high_price_kills_adoption():
    personas = generate_personas(50, seed=1)
    cheap = _spec()
    expensive = ProductSpec(
        name="Pricey",
        category="study",
        features=["a"],
        price_monthly=200.0,
        target_segment="students",
        substitutes=[],
    )
    cheap_report = build_report(run_simulation(cheap, personas, days=30, seed=1))
    expensive_report = build_report(
        run_simulation(expensive, personas, days=30, seed=1)
    )
    assert expensive_report.adoption_rate < cheap_report.adoption_rate


def test_actions_are_valid_enum_values():
    personas = generate_personas(20, seed=3)
    result = run_simulation(_spec(), personas, days=15, seed=3)
    for event in result.events:
        assert event.action in Action


# ---------- Mechanism integration tests ----------

def test_mechanism_spec_runs_without_error():
    personas = generate_personas(50, seed=1)
    result = run_simulation(_mech_spec(), personas, days=30, seed=1)
    assert len(result.events) == 50 * 31


def test_report_has_survivability_fields_when_mechanisms_present():
    personas = generate_personas(50, seed=1)
    report = build_report(run_simulation(_mech_spec(), personas, days=30, seed=1))
    assert report.survivability_score is not None
    assert report.decision in ("Build", "Test", "Drop")
    assert report.mechanism_scores is not None
    assert report.archetype_survivability is not None
    assert 0.0 <= report.survivability_score <= 1.0


def test_report_no_survivability_without_mechanisms():
    personas = generate_personas(50, seed=1)
    report = build_report(run_simulation(_spec(), personas, days=30, seed=1))
    assert report.survivability_score is None
    assert report.decision is None
    assert report.mechanism_scores is None


def test_high_R_boosts_adoption():
    personas = generate_personas(100, seed=42)
    high_r = build_report(run_simulation(_mech_spec(R=0.9), personas, days=30, seed=42))
    low_r = build_report(run_simulation(_mech_spec(R=0.05), personas, days=30, seed=42))
    assert high_r.adoption_rate > low_r.adoption_rate


def test_high_U_and_W_improve_retention():
    personas = generate_personas(100, seed=42)
    strong = build_report(run_simulation(_mech_spec(U=0.9, W=0.9), personas, days=30, seed=42))
    weak = build_report(run_simulation(_mech_spec(U=0.05, W=0.05), personas, days=30, seed=42))
    assert strong.viability_score > weak.viability_score


def test_mechanism_simulation_is_deterministic():
    personas = generate_personas(50, seed=7)
    spec = _mech_spec()
    r1 = build_report(run_simulation(spec, personas, days=30, seed=7))
    r2 = build_report(run_simulation(spec, personas, days=30, seed=7))
    assert r1.survivability_score == r2.survivability_score
    assert r1.retention_curve == r2.retention_curve
