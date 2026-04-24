from __future__ import annotations

import random

from .models import Action, DecisionEvent, PersonaState, ProductSpec

PRICE_BENCHMARK = 20.0
DAILY_SATISFACTION_GAIN = 0.12
DISTRACTION_COST_BY_PHASE = {"onboarding": 0.05, "retention": 0.15, "habit": 0.08}
ABANDON_THRESHOLD = 0.25
SWITCH_THRESHOLD = 0.35


def _phase(day: int) -> str:
    if day == 0:
        return "onboarding"
    if day <= 7:
        return "retention"
    return "habit"


def decide(
    state: PersonaState,
    product: ProductSpec,
    day: int,
    rng: random.Random,
) -> DecisionEvent:
    p = state.persona
    phase = _phase(day)

    m = product.mechanisms
    if m is not None:
        daily_gain = DAILY_SATISFACTION_GAIN * (0.7 + 0.6 * m.U)
        phase_cost = {k: v * (1 - 0.5 * m.W) for k, v in DISTRACTION_COST_BY_PHASE.items()}
        abandon_thresh = max(0.1, ABANDON_THRESHOLD - 0.2 * m.R)
        r_boost = 0.2 * m.R
    else:
        daily_gain = DAILY_SATISFACTION_GAIN
        phase_cost = DISTRACTION_COST_BY_PHASE
        abandon_thresh = ABANDON_THRESHOLD
        r_boost = 0.0

    if state.abandoned or state.switched_to is not None:
        return DecisionEvent(
            day=day,
            persona_id=p.id,
            action=Action.ABANDON,
            reason="already off product",
        )

    if not state.engaged:
        price_pressure = min(product.price_monthly / PRICE_BENCHMARK, 1.0)
        cost = p.price_sensitivity * price_pressure
        appeal = 0.55 * p.motivation + 0.45 * p.novelty_bias
        try_score = appeal - cost + rng.uniform(-0.1, 0.1) + r_boost
        if try_score > 0.35:
            state.engaged = True
            state.days_active = 1
            state.satisfaction = 0.3 * p.motivation
            return DecisionEvent(
                day=day,
                persona_id=p.id,
                action=Action.TRY,
                reason=f"try_score={try_score:.2f}",
            )
        return DecisionEvent(
            day=day,
            persona_id=p.id,
            action=Action.ABANDON,
            reason=f"never tried (try_score={try_score:.2f})",
        )

    distraction = phase_cost[phase]
    state.satisfaction += daily_gain * p.attention_span
    state.satisfaction -= distraction * (1 - p.motivation)
    state.satisfaction = max(0.0, min(1.0, state.satisfaction))
    state.days_active += 1

    if state.satisfaction < abandon_thresh and rng.random() < (1 - p.motivation):
        state.abandoned = True
        return DecisionEvent(
            day=day,
            persona_id=p.id,
            action=Action.ABANDON,
            reason=f"satisfaction={state.satisfaction:.2f} below {ABANDON_THRESHOLD}",
        )

    switch_pull = p.novelty_bias * (1 - p.substitute_loyalty)
    if (
        product.substitutes
        and state.satisfaction < SWITCH_THRESHOLD
        and switch_pull > 0.5
        and rng.random() < switch_pull * 0.5
    ):
        state.switched_to = rng.choice(product.substitutes)
        return DecisionEvent(
            day=day,
            persona_id=p.id,
            action=Action.SWITCH,
            reason=f"switched to {state.switched_to} (pull={switch_pull:.2f})",
        )

    return DecisionEvent(
        day=day,
        persona_id=p.id,
        action=Action.CONTINUE,
        reason=f"satisfaction={state.satisfaction:.2f}",
    )
