from __future__ import annotations

import pytest

from kne_guards.models import MechanismScores
from kne_guards.survivability import (
    ALPHA_MULTIPLIERS,
    BUILD_THRESHOLD,
    DROP_THRESHOLD,
    GAMMA,
    KILLER_PENALTY,
    KILLER_THRESHOLD,
    STRATEGY_WEIGHTS,
    compute_survivability,
)


def _scores(**kwargs) -> MechanismScores:
    defaults = {"R": 0.5, "U": 0.5, "W": 0.5, "F": 0.5, "M": 0.5}
    defaults.update(kwargs)
    return MechanismScores(**{k: v for k, v in defaults.items() if k != "strategy"},
                           strategy=kwargs.get("strategy", "balanced"))


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
    expected = min(1.0, 0.4 + GAMMA * 0.5)
    assert abs(result.mechanism_scores["F_prime"] - expected) < 1e-9


def test_f_prime_clamped_at_one() -> None:
    m = _scores(F=0.9, M=1.0)
    result = compute_survivability(m)
    assert result.mechanism_scores["F_prime"] == 1.0


# ---------- Alpha clamp ----------

def test_alpha_clamp_never_exceeds_one() -> None:
    m = _scores(W=1.0, strategy="workflow")
    result = compute_survivability(m, strategy="workflow")
    grinder = result.archetype_survivability["grinder"]
    assert grinder.scores["W"] <= 1.0


# ---------- Strategy-aware killer detection ----------

def test_killer_only_on_load_bearing_dimension() -> None:
    # W is very weak but for a viral strategy W is not load-bearing (weight=0.10 < 0.20)
    m = _scores(W=0.05, M=0.8, F=0.7, strategy="viral")
    result = compute_survivability(m, strategy="viral")
    # No archetype should have W as an active killer under viral strategy
    for arch_surv in result.archetype_survivability.values():
        assert "W" not in arch_surv.active_killers


def test_killer_fires_on_load_bearing_dimension() -> None:
    # W is load-bearing for workflow strategy (weight=0.40); burnout alpha_W=0.6
    # burnout W score = 0.6 * 0.05 = 0.03 < KILLER_THRESHOLD
    m = _scores(W=0.05, strategy="workflow")
    result = compute_survivability(m, strategy="workflow")
    assert "W" in result.archetype_survivability["burnout"].active_killers


def test_killer_penalty_reduces_score() -> None:
    # replacement strategy: R is load-bearing (weight=0.45)
    # burnout alpha_R=0.7; R=0.05 → 0.035 < KILLER_THRESHOLD → penalty applies
    m_weak_R = _scores(R=0.05, strategy="replacement")
    m_ok_R   = _scores(R=0.5,  strategy="replacement")
    r_weak = compute_survivability(m_weak_R, strategy="replacement")
    r_ok   = compute_survivability(m_ok_R,   strategy="replacement")
    assert r_weak.S_aggregate < r_ok.S_aggregate


# ---------- Dominant-strength products score well ----------

def test_viral_product_with_dominant_M_scores_well() -> None:
    # High M, low W — should score well under viral strategy
    m = _scores(M=0.9, F=0.7, R=0.2, U=0.3, W=0.1, strategy="viral")
    result = compute_survivability(m, strategy="viral")
    assert result.S_aggregate > 0.5


def test_same_product_penalised_under_wrong_strategy() -> None:
    # A viral product (high M, low W) scores worse under workflow strategy
    m_raw = dict(M=0.9, F=0.7, R=0.2, U=0.3, W=0.1)
    viral_score = compute_survivability(_scores(**m_raw, strategy="viral"), strategy="viral").S_aggregate
    workflow_score = compute_survivability(_scores(**m_raw, strategy="workflow"), strategy="workflow").S_aggregate
    assert viral_score > workflow_score


def test_workflow_product_with_dominant_W_scores_well() -> None:
    m = _scores(W=0.9, R=0.6, U=0.5, F=0.2, M=0.1, strategy="workflow")
    result = compute_survivability(m, strategy="workflow")
    assert result.S_aggregate > 0.5


# ---------- Decision thresholds ----------

def test_decision_build() -> None:
    m = _scores(R=0.95, U=0.95, W=0.95, F=0.95, M=0.95)
    result = compute_survivability(m)
    assert result.decision == "Build"


def test_decision_drop() -> None:
    m = _scores(R=0.05, U=0.05, W=0.05, F=0.05, M=0.05)
    result = compute_survivability(m)
    assert result.decision == "Drop"


def test_decision_reflects_dominant_strength() -> None:
    # Content strategy with dominant U; W is not catastrophically low (0.25 clears killers)
    # A weak-but-not-killer W should not override a strong U
    m = _scores(U=0.9, R=0.3, W=0.25, F=0.3, M=0.2, strategy="content")
    result = compute_survivability(m, strategy="content")
    assert result.decision in ("Build", "Test")


# ---------- Aggregate formula (no floor term) ----------

def test_aggregate_is_simple_mean() -> None:
    m = _scores(R=0.6, U=0.6, W=0.6, F=0.6, M=0.6)
    result = compute_survivability(m)
    sa_values = [v.S_a for v in result.archetype_survivability.values()]
    expected = sum(sa_values) / len(sa_values)
    assert abs(result.S_aggregate - expected) < 1e-9


# ---------- Unknown strategy falls back to balanced ----------

def test_unknown_strategy_falls_back_to_balanced() -> None:
    m = _scores()
    result = compute_survivability(m, strategy="nonexistent")
    assert result.strategy == "balanced"


# ---------- Growth factor ----------

def test_growth_factor_weak_product() -> None:
    m = _scores(R=0.1, U=0.1, W=0.1, M=0.2)
    result = compute_survivability(m)
    assert result.growth_factor < 1.0 + m.M


def test_growth_factor_strong_product() -> None:
    m = _scores(R=0.9, U=0.9, W=0.9, M=0.8)
    result = compute_survivability(m)
    assert result.growth_factor > 1.0


# ---------- Pure function / determinism ----------

def test_survivability_is_deterministic() -> None:
    m = _scores(R=0.6, U=0.4, W=0.7, F=0.3, M=0.5)
    r1 = compute_survivability(m)
    r2 = compute_survivability(m)
    assert r1.S_aggregate == r2.S_aggregate
    assert r1.decision == r2.decision
    assert r1.active_killers == r2.active_killers
