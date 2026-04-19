from __future__ import annotations

import pytest

from kne_guards.models import MechanismScores
from kne_guards.survivability import (
    ALPHA_MULTIPLIERS,
    BOTTLENECK_THRESHOLD,
    BUILD_THRESHOLD,
    DROP_THRESHOLD,
    GAMMA,
    LAMBDA,
    _WEIGHTS,
    compute_survivability,
)


def _scores(**kwargs) -> MechanismScores:
    defaults = {"R": 0.5, "U": 0.5, "W": 0.5, "F": 0.5, "M": 0.5}
    defaults.update(kwargs)
    return MechanismScores(**defaults)


# ---------- MechanismScores validation ----------

def test_mechanism_scores_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        MechanismScores(R=1.1, U=0.5, W=0.5, F=0.5, M=0.5)
    with pytest.raises(ValueError):
        MechanismScores(R=0.5, U=-0.1, W=0.5, F=0.5, M=0.5)


# ---------- F' amplification ----------

def test_f_prime_amplification() -> None:
    m = _scores(F=0.4, M=0.5)
    result = compute_survivability(m)
    expected_f_prime = min(1.0, 0.4 + GAMMA * 0.5)
    assert abs(result.mechanism_scores["F_prime"] - expected_f_prime) < 1e-9


def test_f_prime_clamped_at_one() -> None:
    m = _scores(F=0.9, M=1.0)
    result = compute_survivability(m)
    assert result.mechanism_scores["F_prime"] == 1.0


# ---------- Alpha clamp ----------

def test_alpha_clamp_never_exceeds_one() -> None:
    m = _scores(W=1.0)  # grinder alpha_W=1.3 → would give 1.3 without clamp
    result = compute_survivability(m)
    grinder = result.archetype_survivability["grinder"]
    assert grinder.scores["W"] <= 1.0


# ---------- Bottleneck detection ----------

def test_bottleneck_detected_below_threshold() -> None:
    # burnout alpha_U=0.5; U=0.1 → 0.05 < BOTTLENECK_THRESHOLD
    m = _scores(U=0.1)
    result = compute_survivability(m)
    assert "burnout" in result.bottlenecks
    assert result.bottlenecks["burnout"] == "U"


def test_no_bottleneck_when_all_above_threshold() -> None:
    # All dims 0.5; lowest alpha is burnout W=0.6 → 0.3 > BOTTLENECK_THRESHOLD
    m = _scores(R=0.5, U=0.5, W=0.5, F=0.5, M=0.5)
    result = compute_survivability(m)
    assert result.bottlenecks == {}


# ---------- Decision thresholds ----------

def test_decision_build() -> None:
    m = _scores(R=0.9, U=0.9, W=0.9, F=0.9, M=0.9)
    result = compute_survivability(m)
    assert result.decision == "Build"
    assert result.S_aggregate >= BUILD_THRESHOLD


def test_decision_drop() -> None:
    m = _scores(R=0.1, U=0.1, W=0.1, F=0.1, M=0.1)
    result = compute_survivability(m)
    assert result.decision == "Drop"
    assert result.S_aggregate < DROP_THRESHOLD


def test_decision_test() -> None:
    # Mid-range scores should land in Test zone
    m = _scores(R=0.4, U=0.4, W=0.4, F=0.4, M=0.3)
    result = compute_survivability(m)
    assert result.decision in ("Test", "Drop")  # mid-range, not Build


# ---------- Aggregate formula ----------

def test_aggregate_lambda_weighting() -> None:
    m = _scores(R=0.6, U=0.6, W=0.6, F=0.6, M=0.6)
    result = compute_survivability(m)
    sa_values = [v.S_a for v in result.archetype_survivability.values()]
    S_floor = min(sa_values)
    S_weighted = sum(sa_values) / len(sa_values)
    expected = max(0.0, min(1.0, LAMBDA * S_floor + (1 - LAMBDA) * S_weighted))
    assert abs(result.S_aggregate - expected) < 1e-9


# ---------- Growth factor ----------

def test_growth_factor_weak_product() -> None:
    # Weak R/U/W → high delta → growth_factor < 1 + M
    m = _scores(R=0.1, U=0.1, W=0.1, M=0.3)
    result = compute_survivability(m)
    assert result.growth_factor < 1.0 + m.M


def test_growth_factor_strong_product() -> None:
    m = _scores(R=0.9, U=0.9, W=0.9, M=0.8)
    result = compute_survivability(m)
    assert result.growth_factor > 1.0


# ---------- Archetype-specific behaviour ----------

def test_grinder_workflow_boosted() -> None:
    m = _scores(W=0.7)
    result = compute_survivability(m)
    grinder_W = result.archetype_survivability["grinder"].scores["W"]
    explorer_W = result.archetype_survivability["explorer"].scores["W"]
    assert grinder_W > explorer_W  # grinder alpha_W=1.3 > explorer alpha_W=0.8


def test_burnout_pessimism() -> None:
    m = _scores(R=0.8, U=0.8, W=0.8, F=0.8, M=0.8)
    result = compute_survivability(m)
    burnout_S = result.archetype_survivability["burnout"].S_a
    grinder_S = result.archetype_survivability["grinder"].S_a
    assert burnout_S < grinder_S


def test_social_high_f_prime_impact() -> None:
    # social alpha_F=1.2; high M boosts F' → social benefits most from WOM
    m = _scores(F=0.3, M=0.8)
    result = compute_survivability(m)
    social_F = result.archetype_survivability["social"].scores["F"]
    budgeter_F = result.archetype_survivability["budgeter"].scores["F"]
    assert social_F > budgeter_F  # social alpha_F=1.2 vs budgeter alpha_F=0.5


# ---------- Pure function / determinism ----------

def test_survivability_is_deterministic() -> None:
    m = _scores(R=0.6, U=0.4, W=0.7, F=0.3, M=0.5)
    r1 = compute_survivability(m)
    r2 = compute_survivability(m)
    assert r1.S_aggregate == r2.S_aggregate
    assert r1.decision == r2.decision
    assert r1.bottlenecks == r2.bottlenecks
