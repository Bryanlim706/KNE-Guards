from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Action(str, Enum):
    TRY = "try"
    CONTINUE = "continue"
    ABANDON = "abandon"
    SWITCH = "switch"


@dataclass
class MechanismScores:
    R: float  # replacement cycle strength
    U: float  # update cycle strength
    W: float  # workflow integration depth
    F: float  # baseline user refresh
    M: float  # word-of-mouth propagation
    strategy: str = "balanced"  # product strategy archetype assigned by the evaluator

    def __post_init__(self) -> None:
        for name, val in [("R", self.R), ("U", self.U), ("W", self.W), ("F", self.F), ("M", self.M)]:
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"MechanismScores.{name}={val!r} must be in [0, 1]")


@dataclass
class ProductSpec:
    name: str
    category: str
    features: list[str]
    price_monthly: float
    target_segment: str
    substitutes: list[str] = field(default_factory=list)
    mechanisms: MechanismScores | None = field(default=None)


@dataclass
class Persona:
    id: str
    archetype: str
    attention_span: float
    motivation: float
    price_sensitivity: float
    novelty_bias: float
    substitute_loyalty: float


@dataclass
class PersonaState:
    persona: Persona
    engaged: bool = False
    days_active: int = 0
    satisfaction: float = 0.0
    abandoned: bool = False
    switched_to: str | None = None


@dataclass
class DecisionEvent:
    day: int
    persona_id: str
    action: Action
    reason: str


Phase = Literal["onboarding", "retention", "habit"]
