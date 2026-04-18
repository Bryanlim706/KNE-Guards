from __future__ import annotations

from kne_guards.models import Action, ProductSpec
from kne_guards.personas import generate_personas
from kne_guards.simulation import run_simulation
from kne_guards.tracking import build_report


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
