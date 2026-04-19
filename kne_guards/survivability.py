from __future__ import annotations

from dataclasses import dataclass, field

from .models import MechanismScores

# Survivability weight vector
W_R, W_U, W_W, W_F = 0.30, 0.25, 0.25, 0.20

# Word-of-mouth amplification of organic inflow
GAMMA = 0.3

# Bottleneck fragility threshold — below this a product is fragile for that archetype
BOTTLENECK_THRESHOLD = 0.2

# Risk-sensitivity in aggregation: higher = more weight on worst-case archetype
LAMBDA = 0.4

# Decision thresholds
BUILD_THRESHOLD = 0.65
DROP_THRESHOLD = 0.40

# Per-archetype α multipliers derived from behavioral profiles in personas.py
ALPHA_MULTIPLIERS: dict[str, dict[str, float]] = {
    "grinder":  {"R": 0.9, "U": 0.8, "W": 1.3, "F": 1.0},
    "explorer": {"R": 1.1, "U": 1.2, "W": 0.8, "F": 1.0},
    "burnout":  {"R": 0.7, "U": 0.5, "W": 0.6, "F": 0.8},
    "budgeter": {"R": 0.9, "U": 0.9, "W": 1.0, "F": 0.5},
    "social":   {"R": 1.0, "U": 1.0, "W": 0.9, "F": 1.2},
}

_WEIGHTS = {"R": W_R, "U": W_U, "W": W_W, "F": W_F}


@dataclass
class ArchetypeSurvivability:
    archetype: str
    scores: dict[str, float]     # constrained per-dim scores after alpha
    S_a: float                   # weighted survivability for this archetype
    bottleneck_dim: str | None   # weakest dimension, or None if above threshold
    bottleneck_value: float      # value of the weakest dimension


@dataclass
class SurvivabilityResult:
    mechanism_scores: dict[str, float]                         # raw + F_prime
    archetype_survivability: dict[str, ArchetypeSurvivability]
    bottlenecks: dict[str, str]                                # {archetype: dim} for fragile ones
    S_aggregate: float
    decision: str                                              # "Build" | "Test" | "Drop"
    growth_factor: float


def compute_survivability(m: MechanismScores) -> SurvivabilityResult:
    F_prime = min(1.0, m.F + GAMMA * m.M)
    base = {"R": m.R, "U": m.U, "W": m.W, "F": F_prime}

    mechanism_scores = {**base, "M": m.M, "F_prime": F_prime}

    archetype_survivability: dict[str, ArchetypeSurvivability] = {}
    bottlenecks: dict[str, str] = {}

    for archetype, alphas in ALPHA_MULTIPLIERS.items():
        scores = {dim: min(1.0, alphas[dim] * base[dim]) for dim in base}
        S_a = sum(_WEIGHTS[dim] * scores[dim] for dim in scores)
        min_dim = min(scores, key=lambda d: scores[d])
        min_val = scores[min_dim]
        bottleneck_dim = min_dim if min_val < BOTTLENECK_THRESHOLD else None
        if bottleneck_dim is not None:
            bottlenecks[archetype] = bottleneck_dim
        archetype_survivability[archetype] = ArchetypeSurvivability(
            archetype=archetype,
            scores=scores,
            S_a=S_a,
            bottleneck_dim=bottleneck_dim,
            bottleneck_value=min_val,
        )

    sa_values = [v.S_a for v in archetype_survivability.values()]
    S_floor = min(sa_values)
    S_weighted = sum(sa_values) / len(sa_values)
    S_aggregate = max(0.0, min(1.0, LAMBDA * S_floor + (1 - LAMBDA) * S_weighted))

    # Churn derived from structural weakness in engagement dimensions
    delta = (1 - m.R) * 0.1 + (1 - m.U) * 0.1 + (1 - m.W) * 0.1
    growth_factor = 1.0 + m.M - delta

    if S_aggregate >= BUILD_THRESHOLD:
        decision = "Build"
    elif S_aggregate >= DROP_THRESHOLD:
        decision = "Test"
    else:
        decision = "Drop"

    return SurvivabilityResult(
        mechanism_scores=mechanism_scores,
        archetype_survivability=archetype_survivability,
        bottlenecks=bottlenecks,
        S_aggregate=S_aggregate,
        decision=decision,
        growth_factor=growth_factor,
    )
