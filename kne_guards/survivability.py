from __future__ import annotations

from dataclasses import dataclass, field

from .models import MechanismScores

# WOM amplification of organic inflow
GAMMA = 0.3

# A dimension is an active killer only when it falls below this — and only when
# it is load-bearing for the product's strategy (weight >= LOAD_BEARING_CUTOFF).
KILLER_THRESHOLD = 0.10
KILLER_PENALTY = 0.35       # each active killer reduces S_a by this fraction
LOAD_BEARING_CUTOFF = 0.20  # dimensions with weight >= this are load-bearing

# Decision thresholds
BUILD_THRESHOLD = 0.55
DROP_THRESHOLD = 0.38

# Strategy weight profiles — weights reflect which dimensions are structurally
# important for each product archetype. Dimensions irrelevant to the strategy
# carry low weight and are not treated as killers even if weak.
STRATEGY_WEIGHTS: dict[str, dict[str, float]] = {
    # Grows through sharing; embeddedness and replacement matter less
    "viral":       {"R": 0.10, "U": 0.20, "W": 0.10, "F": 0.25, "M": 0.35},
    # Lives inside existing workflows; stickiness via integration and habit
    "workflow":    {"R": 0.20, "U": 0.20, "W": 0.40, "F": 0.10, "M": 0.10},
    # Returns driven by fresh content; W is not load-bearing — habit loop substitutes for it
    "content":     {"R": 0.15, "U": 0.55, "W": 0.10, "F": 0.20, "M": 0.00},
    # Displaces a specific existing tool or behaviour
    "replacement": {"R": 0.45, "U": 0.20, "W": 0.20, "F": 0.10, "M": 0.05},
    # Found through organic channels; lives or dies by discoverability
    "discovery":   {"R": 0.15, "U": 0.15, "W": 0.15, "F": 0.40, "M": 0.15},
    # Default: treats all structural dims as moderately important
    "balanced":    {"R": 0.28, "U": 0.24, "W": 0.24, "F": 0.24, "M": 0.00},
}

# Per-archetype α multipliers derived from behavioral profiles in personas.py
ALPHA_MULTIPLIERS: dict[str, dict[str, float]] = {
    "grinder":  {"R": 0.9, "U": 0.8, "W": 1.3, "F": 1.0, "M": 0.7},
    "explorer": {"R": 1.1, "U": 1.2, "W": 0.8, "F": 1.0, "M": 1.1},
    "burnout":  {"R": 0.7, "U": 0.5, "W": 0.6, "F": 0.8, "M": 0.6},
    "budgeter": {"R": 0.9, "U": 0.9, "W": 1.0, "F": 0.5, "M": 0.8},
    "social":   {"R": 1.0, "U": 1.0, "W": 0.9, "F": 1.2, "M": 1.5},
}


@dataclass
class ArchetypeSurvivability:
    archetype: str
    scores: dict[str, float]      # constrained per-dim scores after alpha
    S_a: float                    # strategy-weighted survivability score
    active_killers: list[str]     # load-bearing dimensions below KILLER_THRESHOLD


@dataclass
class SurvivabilityResult:
    strategy: str
    mechanism_scores: dict[str, float]                          # raw + F_prime
    archetype_survivability: dict[str, ArchetypeSurvivability]
    active_killers: dict[str, list[str]]                        # {archetype: [dims]}
    S_aggregate: float
    decision: str                                               # "Build"|"Test"|"Drop"
    growth_factor: float


def compute_survivability(
    m: MechanismScores,
    strategy: str = "balanced",
) -> SurvivabilityResult:
    if strategy not in STRATEGY_WEIGHTS:
        strategy = "balanced"

    weights = STRATEGY_WEIGHTS[strategy]
    load_bearing = {dim for dim, w in weights.items() if w >= LOAD_BEARING_CUTOFF}

    F_prime = min(1.0, m.F + GAMMA * m.M)
    # Build the full scored vector including M (needed for social alpha and killer check)
    base = {"R": m.R, "U": m.U, "W": m.W, "F": F_prime, "M": m.M}
    mechanism_scores = {**base, "F_prime": F_prime}

    archetype_survivability: dict[str, ArchetypeSurvivability] = {}
    all_killers: dict[str, list[str]] = {}

    for archetype, alphas in ALPHA_MULTIPLIERS.items():
        scores = {dim: min(1.0, alphas[dim] * base[dim]) for dim in base}

        # Weighted score using strategy weights
        S_a = sum(weights.get(dim, 0.0) * scores[dim] for dim in scores)

        # Killer penalty — only load-bearing dimensions can be killers
        killers = [dim for dim in load_bearing if scores[dim] < KILLER_THRESHOLD]
        for _ in killers:
            S_a *= (1 - KILLER_PENALTY)
        S_a = max(0.0, min(1.0, S_a))

        if killers:
            all_killers[archetype] = killers

        archetype_survivability[archetype] = ArchetypeSurvivability(
            archetype=archetype,
            scores=scores,
            S_a=S_a,
            active_killers=killers,
        )

    S_aggregate = sum(v.S_a for v in archetype_survivability.values()) / len(archetype_survivability)
    S_aggregate = max(0.0, min(1.0, S_aggregate))

    delta = (1 - m.R) * 0.1 + (1 - m.U) * 0.1 + (1 - m.W) * 0.1
    growth_factor = 1.0 + m.M - delta

    if S_aggregate >= BUILD_THRESHOLD:
        decision = "Build"
    elif S_aggregate >= DROP_THRESHOLD:
        decision = "Test"
    else:
        decision = "Drop"

    return SurvivabilityResult(
        strategy=strategy,
        mechanism_scores=mechanism_scores,
        archetype_survivability=archetype_survivability,
        active_killers=all_killers,
        S_aggregate=S_aggregate,
        decision=decision,
        growth_factor=growth_factor,
    )
