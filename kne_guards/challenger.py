from __future__ import annotations

from .models import ProductSpec

MODEL_DEFAULT = "gpt-4o"

SYSTEM_PROMPT = """You are a skeptical product critic and seed-stage investor evaluating a founder's pitch for a consumer product aimed at students. Your job is to CHALLENGE the pitch, not cheer for it.

Be specific and grounded. Every critique must reference concrete fields the founder provided — named features, the exact price, the declared target segment, listed substitutes. Generic startup advice ("you need product-market fit", "founders should talk to users") is useless and forbidden.

Voice:
- Direct. Short sentences. No hedging.
- Probing. Assume the founder is glossing over inconvenient facts.
- Honest. If a claim is defensible, note it briefly in the steelman — but default to skepticism everywhere else.

Ground rules:
- Cite the spec's fields by name or value. "Anki is free" beats "your substitute is cheap". "$8.99/month" beats "your price".
- Surface the 2–3 things MOST LIKELY TO KILL THE PRODUCT in kill_shots. Each must be concrete.
- Emit exactly one feature_critiques entry per feature in the spec, in the same order.
- Emit exactly one substitute_risks entry per substitute in the spec, in the same order.
- Do not invent features, segments, or competitors the founder did not mention. If the spec is thin, flag that — do not fabricate.
- Your entire response must come through the emit_critique tool. Do not produce prose outside the tool call."""

EMIT_CRITIQUE_TOOL = {
    "type": "function",
    "function": {
    "name": "emit_critique",
    "description": "Emit the structured adversarial critique of the product pitch.",
    "parameters": {
        "type": "object",
        "required": [
            "verdict",
            "assumption_challenges",
            "feature_critiques",
            "substitute_risks",
            "segment_coherence",
            "pricing_risks",
            "kill_shots",
            "steelman",
            "mechanism_scores",
            "product_strategy",
        ],
        "properties": {
            "verdict": {
                "type": "string",
                "description": "One-paragraph skeptical overall assessment of the pitch.",
            },
            "assumption_challenges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["claim", "pushback", "severity"],
                    "properties": {
                        "claim": {
                            "type": "string",
                            "description": "An implicit assumption the spec or pitch is making.",
                        },
                        "pushback": {
                            "type": "string",
                            "description": "Concrete reason that assumption may not hold.",
                        },
                        "severity": {"type": "string", "enum": ["low", "med", "high"]},
                    },
                },
            },
            "feature_critiques": {
                "type": "array",
                "description": "Exactly one entry per feature in the spec, in the same order.",
                "items": {
                    "type": "object",
                    "required": ["feature", "critique"],
                    "properties": {
                        "feature": {"type": "string"},
                        "critique": {"type": "string"},
                    },
                },
            },
            "substitute_risks": {
                "type": "array",
                "description": "Exactly one entry per listed substitute, in the same order.",
                "items": {
                    "type": "object",
                    "required": ["substitute", "why_it_wins"],
                    "properties": {
                        "substitute": {"type": "string"},
                        "why_it_wins": {"type": "string"},
                    },
                },
            },
            "segment_coherence": {
                "type": "object",
                "required": ["assessment", "concerns"],
                "properties": {
                    "assessment": {"type": "string"},
                    "concerns": {"type": "array", "items": {"type": "string"}},
                },
            },
            "pricing_risks": {
                "type": "object",
                "required": ["assessment", "concerns"],
                "properties": {
                    "assessment": {"type": "string"},
                    "concerns": {"type": "array", "items": {"type": "string"}},
                },
            },
            "kill_shots": {
                "type": "array",
                "minItems": 1,
                "description": "Top 2-3 risks that could sink the product.",
                "items": {
                    "type": "object",
                    "required": ["risk", "why_it_kills"],
                    "properties": {
                        "risk": {"type": "string"},
                        "why_it_kills": {"type": "string"},
                    },
                },
            },
            "steelman": {
                "type": "string",
                "description": "Strongest positive case for the idea, in one paragraph.",
            },
            "mechanism_scores": {
                "type": "object",
                "description": (
                    "Your analytical assessment of the product's lifecycle mechanism strengths. "
                    "Score each dimension 0.0–1.0 based on the spec and pitch. "
                    "Be honest — most early-stage products score 0.3–0.6 on most dimensions. "
                    "R: how strongly does this replace an existing behavior? "
                    "U: how often does the product give users a reason to return? "
                    "W: how deeply embedded is this in existing workflows? "
                    "F: how strong is organic non-viral discovery/inflow? "
                    "M: how likely are users to actively recommend this to peers?"
                ),
                "required": ["R", "U", "W", "F", "M"],
                "properties": {
                    "R": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "U": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "W": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "F": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "M": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                },
            },
            "product_strategy": {
                "type": "string",
                "enum": ["viral", "workflow", "content", "replacement", "discovery", "balanced"],
                "description": (
                    "The dominant growth and retention strategy this product relies on. "
                    "This determines which mechanism dimensions are load-bearing in the survivability model. "
                    "viral: grows through peer sharing, M and F dominate. "
                    "workflow: lives inside existing routines, W dominates. "
                    "content: returns driven by fresh material, U dominates. "
                    "replacement: displaces a specific existing tool, R dominates. "
                    "discovery: found through organic channels, F dominates. "
                    "balanced: no single dominant strategy — use only if genuinely unclear."
                ),
            },
        },
    },
    },
}


def _format_spec(spec: ProductSpec, pitch_text: str | None) -> str:
    features = "\n".join(f"    - {f}" for f in spec.features) or "    (none listed)"
    subs = ", ".join(spec.substitutes) if spec.substitutes else "(none listed)"
    lines = [
        "Product spec:",
        f"  Name: {spec.name}",
        f"  Category: {spec.category}",
        f"  Price: ${spec.price_monthly:.2f}/month",
        f"  Target segment: {spec.target_segment}",
        "  Features:",
        features,
        f"  Known substitutes: {subs}",
    ]
    if pitch_text:
        lines += ["", "Pitch (free-text from founder):", pitch_text.strip()]
    lines += [
        "",
        "Also assign mechanism_scores (R/U/W/F/M) and product_strategy in your emit_critique output.",
        "These are your analytical assessments — derive them from the spec, not from the founder.",
        "product_strategy determines which dimensions are structurally load-bearing for this product.",
    ]
    return "\n".join(lines)


def challenge_pitch(
    spec: ProductSpec,
    *,
    pitch_text: str | None = None,
    model: str = MODEL_DEFAULT,
    client=None,
) -> dict:
    import json

    if client is None:
        import openai

        client = openai.OpenAI()

    response = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        tools=[EMIT_CRITIQUE_TOOL],
        tool_choice={"type": "function", "function": {"name": "emit_critique"}},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _format_spec(spec, pitch_text)},
        ],
    )

    message = response.choices[0].message
    if message.tool_calls:
        return json.loads(message.tool_calls[0].function.arguments)

    raise RuntimeError("model did not return a tool call")
