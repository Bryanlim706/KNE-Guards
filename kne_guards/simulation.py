from __future__ import annotations

import random
from dataclasses import dataclass

from .decisions import decide
from .models import DecisionEvent, Persona, PersonaState, ProductSpec


@dataclass
class SimulationResult:
    product: ProductSpec
    events: list[DecisionEvent]
    final_states: list[PersonaState]
    days: int


def run_simulation(
    product: ProductSpec,
    personas: list[Persona],
    days: int = 30,
    seed: int = 42,
) -> SimulationResult:
    rng = random.Random(seed)
    states = [PersonaState(persona=p) for p in personas]
    events: list[DecisionEvent] = []

    for day in range(days + 1):
        for state in states:
            events.append(decide(state, product, day, rng))

    return SimulationResult(
        product=product, events=events, final_states=states, days=days
    )
