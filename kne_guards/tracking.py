from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .models import Action
from .simulation import SimulationResult


@dataclass
class Report:
    product_name: str
    days: int
    n_personas: int
    retention_curve: list[float]
    adoption_rate: float
    abandoned_rate: float
    switched_rate: float
    drop_off_by_day: dict[int, int]
    persona_breakdown: dict[str, dict[str, int]]
    viability_score: float
    switched_to: dict[str, int] = field(default_factory=dict)
    # Mechanism layer — only populated when ProductSpec carries mechanism scores
    mechanism_scores: dict[str, float] | None = field(default=None)
    archetype_survivability: dict[str, dict] | None = field(default=None)
    bottlenecks: dict[str, str] | None = field(default=None)
    survivability_score: float | None = field(default=None)
    decision: str | None = field(default=None)


def _retained_on_day(result: SimulationResult, day: int) -> int:
    retained = 0
    for event in result.events:
        if event.day != day:
            continue
        if event.action in (Action.TRY, Action.CONTINUE):
            retained += 1
    return retained


def build_report(result: SimulationResult) -> Report:
    n = len(result.final_states)
    retention_curve = [_retained_on_day(result, d) / n for d in range(result.days + 1)]

    ever_tried = sum(1 for s in result.final_states if s.days_active > 0)
    abandoned = sum(1 for s in result.final_states if s.abandoned)
    switched = sum(1 for s in result.final_states if s.switched_to is not None)

    drop_off_by_day: dict[int, int] = defaultdict(int)
    seen: set[str] = set()
    for event in result.events:
        if event.action == Action.ABANDON and event.persona_id not in seen:
            drop_off_by_day[event.day] += 1
            seen.add(event.persona_id)
        elif event.action == Action.SWITCH and event.persona_id not in seen:
            drop_off_by_day[event.day] += 1
            seen.add(event.persona_id)

    persona_breakdown: dict[str, dict[str, int]] = defaultdict(
        lambda: {"retained": 0, "abandoned": 0, "switched": 0, "total": 0}
    )
    for state in result.final_states:
        bucket = persona_breakdown[state.persona.archetype]
        bucket["total"] += 1
        if state.switched_to is not None:
            bucket["switched"] += 1
        elif state.abandoned or state.days_active == 0:
            bucket["abandoned"] += 1
        else:
            bucket["retained"] += 1

    switched_to = dict(
        Counter(s.switched_to for s in result.final_states if s.switched_to)
    )

    day_30_retention = retention_curve[-1]
    viability = (
        0.5 * day_30_retention + 0.3 * (ever_tried / n) + 0.2 * (1 - switched / n)
    )

    mechanism_scores = None
    archetype_survivability = None
    bottlenecks = None
    survivability_score = None
    decision = None

    if result.product.mechanisms is not None:
        from .survivability import compute_survivability
        surv = compute_survivability(
            result.product.mechanisms,
            strategy=result.product.mechanisms.strategy,
        )
        mechanism_scores = surv.mechanism_scores
        archetype_survivability = {
            arch: {
                "scores": v.scores,
                "S_a": v.S_a,
                "active_killers": v.active_killers,
            }
            for arch, v in surv.archetype_survivability.items()
        }
        bottlenecks = surv.active_killers
        survivability_score = surv.S_aggregate
        decision = surv.decision

    return Report(
        product_name=result.product.name,
        days=result.days,
        n_personas=n,
        retention_curve=retention_curve,
        adoption_rate=ever_tried / n,
        abandoned_rate=abandoned / n,
        switched_rate=switched / n,
        drop_off_by_day=dict(drop_off_by_day),
        persona_breakdown={k: dict(v) for k, v in persona_breakdown.items()},
        viability_score=viability,
        switched_to=switched_to,
        mechanism_scores=mechanism_scores,
        archetype_survivability=archetype_survivability,
        bottlenecks=bottlenecks,
        survivability_score=survivability_score,
        decision=decision,
    )
