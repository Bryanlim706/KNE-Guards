from __future__ import annotations

import random

from .models import Persona

ARCHETYPES = {
    "grinder": dict(
        attention_span=(0.7, 0.9),
        motivation=(0.75, 0.95),
        price_sensitivity=(0.3, 0.6),
        novelty_bias=(0.1, 0.3),
        substitute_loyalty=(0.6, 0.9),
    ),
    "explorer": dict(
        attention_span=(0.4, 0.7),
        motivation=(0.5, 0.75),
        price_sensitivity=(0.4, 0.7),
        novelty_bias=(0.7, 0.95),
        substitute_loyalty=(0.1, 0.35),
    ),
    "burnout": dict(
        attention_span=(0.15, 0.4),
        motivation=(0.2, 0.45),
        price_sensitivity=(0.5, 0.8),
        novelty_bias=(0.3, 0.6),
        substitute_loyalty=(0.3, 0.6),
    ),
    "budgeter": dict(
        attention_span=(0.5, 0.75),
        motivation=(0.55, 0.8),
        price_sensitivity=(0.75, 0.98),
        novelty_bias=(0.2, 0.5),
        substitute_loyalty=(0.5, 0.8),
    ),
    "social": dict(
        attention_span=(0.45, 0.7),
        motivation=(0.5, 0.75),
        price_sensitivity=(0.4, 0.7),
        novelty_bias=(0.45, 0.7),
        substitute_loyalty=(0.35, 0.6),
    ),
}


def generate_personas(n: int, seed: int = 42) -> list[Persona]:
    rng = random.Random(seed)
    archetype_names = list(ARCHETYPES.keys())
    personas: list[Persona] = []
    for i in range(n):
        archetype = archetype_names[i % len(archetype_names)]
        bands = ARCHETYPES[archetype]
        personas.append(
            Persona(
                id=f"p{i:03d}",
                archetype=archetype,
                attention_span=rng.uniform(*bands["attention_span"]),
                motivation=rng.uniform(*bands["motivation"]),
                price_sensitivity=rng.uniform(*bands["price_sensitivity"]),
                novelty_bias=rng.uniform(*bands["novelty_bias"]),
                substitute_loyalty=rng.uniform(*bands["substitute_loyalty"]),
            )
        )
    return personas
