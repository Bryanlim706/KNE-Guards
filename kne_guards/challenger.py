from __future__ import annotations

import json
import os

from .models import ProductSpec

OPENAI_MODEL_DEFAULT = "gpt-4o"
ANTHROPIC_MODEL_DEFAULT = "claude-sonnet-4-6"


def _active_provider(client=None) -> str:
    if client is not None:
        module = type(client).__module__ or ""
        return "anthropic" if "anthropic" in module else "openai"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError(
        "No API key set. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env."
    )


def is_ready() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _model_default_for(provider: str) -> str:
    return ANTHROPIC_MODEL_DEFAULT if provider == "anthropic" else OPENAI_MODEL_DEFAULT


def _anthropic_tool(openai_tool: dict) -> dict:
    fn = openai_tool["function"]
    return {
        "name": fn["name"],
        "description": fn["description"],
        "input_schema": fn["parameters"],
    }


def _run_tool(
    *,
    system_prompt: str,
    user_message: str,
    tool: dict,
    model: str | None = None,
    max_tokens: int = 4096,
    client=None,
) -> dict:
    provider = _active_provider(client)
    tool_name = tool["function"]["name"]
    effective_model = model or _model_default_for(provider)

    if provider == "anthropic":
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        response = client.messages.create(
            model=effective_model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=[_anthropic_tool(tool)],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user_message}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return block.input
        raise RuntimeError("model did not return a tool_use block")

    if client is None:
        from openai import OpenAI

        client = OpenAI()
    response = client.chat.completions.create(
        model=effective_model,
        max_tokens=max_tokens,
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": tool_name}},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    for choice in response.choices:
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                if tc.function.name == tool_name:
                    return json.loads(tc.function.arguments)
    raise RuntimeError("model did not return a tool_use block")


def _initial_default_model() -> str:
    try:
        return _model_default_for(_active_provider())
    except RuntimeError:
        return OPENAI_MODEL_DEFAULT


MODEL_DEFAULT = _initial_default_model()

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
                            "severity": {
                                "type": "string",
                                "enum": ["low", "med", "high"],
                            },
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
                    "enum": [
                        "viral",
                        "workflow",
                        "content",
                        "replacement",
                        "discovery",
                        "balanced",
                    ],
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

EXPRESSION_SYSTEM_PROMPT = """You are a product storytelling editor helping a founder explain a student-focused product clearly before they turn it into a pitch deck.

Your job is to make the idea more concrete, specific, and believable without inventing evidence or features that are not in the brief.

Rules:
- Ground every output in the exact product name, features, price, target segment, and substitutes provided.
- Keep the writing crisp, founder-like, and easy to reuse in a pitch deck.
- Do not use hypey claims like "revolutionary" or "game-changing".
- Do not fabricate traction, metrics, partnerships, or user quotes.
- If the brief is thin, help structure it anyway and note the missing sharpness through the wording.
- Your entire response must come through the emit_expression_help tool."""

EMIT_EXPRESSION_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_expression_help",
        "description": "Emit structured language that helps a founder explain the product more clearly.",
        "parameters": {
            "type": "object",
            "required": [
                "founder_framing",
                "elevator_pitch",
                "pitch_deck_opening",
                "audience_pains",
                "differentiators",
                "story_beats",
            ],
            "properties": {
                "founder_framing": {
                    "type": "string",
                    "description": "A short paragraph that frames the idea clearly and concretely.",
                },
                "elevator_pitch": {
                    "type": "string",
                    "description": "A concise, improved pitch the founder can reuse directly.",
                },
                "pitch_deck_opening": {
                    "type": "string",
                    "description": "A sharper opening line for the first part of a pitch deck.",
                },
                "audience_pains": {
                    "type": "array",
                    "description": "Concrete user pains this product is addressing.",
                    "items": {"type": "string"},
                },
                "differentiators": {
                    "type": "array",
                    "description": "Specific points that distinguish the product from substitutes.",
                    "items": {"type": "string"},
                },
                "story_beats": {
                    "type": "array",
                    "description": "Short bullet-like beats the founder can use to tell the story in a deck.",
                    "items": {"type": "string"},
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


def _format_expression_prompt(spec: ProductSpec, pitch_text: str | None) -> str:
    features = "\n".join(f"    - {f}" for f in spec.features) or "    (none listed)"
    substitutes = ", ".join(spec.substitutes) if spec.substitutes else "(none listed)"
    lines = [
        "Help the founder express this idea more clearly before they build a pitch deck.",
        "",
        "Product spec:",
        f"  Name: {spec.name}",
        f"  Category: {spec.category}",
        f"  Price: ${spec.price_monthly:.2f}/month",
        f"  Target segment: {spec.target_segment}",
        "  Features:",
        features,
        f"  Known substitutes: {substitutes}",
    ]
    if pitch_text:
        lines += ["", "Current founder draft:", pitch_text.strip()]
    else:
        lines += ["", "Current founder draft: (none provided)"]
    lines += [
        "",
        "Write with enough specificity that the result can be copied into a pitch deck draft.",
    ]
    return "\n".join(lines)


def challenge_pitch(
    spec: ProductSpec,
    *,
    pitch_text: str | None = None,
    model: str | None = None,
    client=None,
) -> dict:
    return _run_tool(
        system_prompt=SYSTEM_PROMPT,
        user_message=_format_spec(spec, pitch_text),
        tool=EMIT_CRITIQUE_TOOL,
        model=model,
        client=client,
    )


def improve_pitch_expression(
    spec: ProductSpec,
    *,
    pitch_text: str | None = None,
    model: str | None = None,
    client=None,
) -> dict:
    return _run_tool(
        system_prompt=EXPRESSION_SYSTEM_PROMPT,
        user_message=_format_expression_prompt(spec, pitch_text),
        tool=EMIT_EXPRESSION_TOOL,
        model=model,
        client=client,
    )


PERSONA_SYSTEM_PROMPT = """You are role-playing as a single synthetic student persona evaluating a product pitch. You are not a founder, not an investor, not a coach — you are a student in the target market reacting honestly, in your own voice.

You will be told which archetype you are and the five parameter bands that define you:
- attention_span: how long you stay focused on any one tool.
- motivation: how willing you are to do work to get a result.
- price_sensitivity: how much price friction blocks you.
- novelty_bias: how much "new and shiny" pulls you in.
- substitute_loyalty: how stuck you are on what you already use.

Stay inside those bands. A low-attention-span burnout does not suddenly grind through a 20-step onboarding. A high-substitute-loyalty grinder does not drop Anki on a whim. A high-price-sensitivity budgeter does not shrug at $12/month.

Ground rules:
- Reference the spec by exact field values. "$8.99/month" not "the price". Name features and substitutes the founder actually listed.
- Do not invent features, prices, segments, or competitors that are not in the spec. If the spec is thin, say the pitch was thin — do not fabricate.
- No hype, no cheerleading, no fabricated traction or quotes.
- biggest_hook.feature must be copied verbatim from the spec's features (or null if nothing fits you).
- likely_substitute.name must be copied verbatim from the spec's substitutes (or null if none were listed).
- biggest_objection.tied_to_param must be the single param that most drives your objection, from the five names above.
- persona_fit_score is a 0.0–1.0 self-assessment of how well this product fits YOU specifically. Most products score 0.2–0.6 for most personas.
- Your entire response must come through the emit_persona_reaction tool. Do not produce prose outside the tool call."""


EMIT_PERSONA_REACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "emit_persona_reaction",
        "description": "Emit this single persona's honest in-voice reaction to the pitch.",
        "parameters": {
            "type": "object",
            "required": [
                "verdict",
                "first_reaction",
                "biggest_hook",
                "biggest_objection",
                "what_would_get_me",
                "likely_substitute",
                "persona_fit_score",
            ],
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["would_try", "skeptical", "pass", "wrong_fit"],
                    "description": "Your overall stance on trying the product.",
                },
                "first_reaction": {
                    "type": "string",
                    "description": "One-to-two sentence gut reaction in your voice.",
                },
                "biggest_hook": {
                    "type": "object",
                    "required": ["feature", "why_it_lands"],
                    "properties": {
                        "feature": {
                            "type": ["string", "null"],
                            "description": "One feature from spec.features verbatim, or null if nothing fits you.",
                        },
                        "why_it_lands": {
                            "type": "string",
                            "description": "Why this matters to you given your param bands.",
                        },
                    },
                },
                "biggest_objection": {
                    "type": "object",
                    "required": ["issue", "tied_to_param", "why"],
                    "properties": {
                        "issue": {
                            "type": "string",
                            "description": "Concrete blocker in your voice.",
                        },
                        "tied_to_param": {
                            "type": "string",
                            "enum": [
                                "attention_span",
                                "motivation",
                                "price_sensitivity",
                                "novelty_bias",
                                "substitute_loyalty",
                            ],
                        },
                        "why": {
                            "type": "string",
                            "description": "Why this param makes the objection sharp for you.",
                        },
                    },
                },
                "what_would_get_me": {
                    "type": "string",
                    "description": "Concrete change to features/price/segment that would flip you to would_try.",
                },
                "likely_substitute": {
                    "type": "object",
                    "required": ["name", "why_it_wins"],
                    "properties": {
                        "name": {
                            "type": ["string", "null"],
                            "description": "One substitute from spec.substitutes verbatim, or null if none listed or none applies.",
                        },
                        "why_it_wins": {
                            "type": ["string", "null"],
                            "description": "Why you would stay with it, or null if not applicable.",
                        },
                    },
                },
                "persona_fit_score": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "0.0–1.0 self-assessment of product fit. Most products score 0.2–0.6.",
                },
            },
        },
    },
}


def _format_persona_prompt(
    spec: ProductSpec,
    *,
    archetype: str,
    bands: dict,
    blurb: str,
    pitch_text: str | None,
) -> str:
    band_lines = []
    for key in (
        "attention_span",
        "motivation",
        "price_sensitivity",
        "novelty_bias",
        "substitute_loyalty",
    ):
        band = bands.get(key)
        if isinstance(band, (list, tuple)) and len(band) == 2:
            band_lines.append(f"    {key}: {band[0]:.2f}–{band[1]:.2f}")
        else:
            band_lines.append(f"    {key}: {band}")
    who = [
        "Who you are:",
        f"  Archetype: {archetype}",
        f"  Blurb: {blurb}",
        "  Param bands:",
        *band_lines,
    ]
    return _format_spec(spec, pitch_text) + "\n\n" + "\n".join(who)


def react_as_persona(
    spec: ProductSpec,
    *,
    archetype: str,
    bands: dict,
    blurb: str,
    pitch_text: str | None = None,
    model: str | None = None,
    client=None,
) -> dict:
    reaction = _run_tool(
        system_prompt=PERSONA_SYSTEM_PROMPT,
        user_message=_format_persona_prompt(
            spec,
            archetype=archetype,
            bands=bands,
            blurb=blurb,
            pitch_text=pitch_text,
        ),
        tool=EMIT_PERSONA_REACTION_TOOL,
        model=model,
        max_tokens=2048,
        client=client,
    )
    hook = reaction.get("biggest_hook") or {}
    if hook.get("feature") and hook["feature"] not in spec.features:
        hook["feature"] = None
    reaction["biggest_hook"] = hook
    sub = reaction.get("likely_substitute") or {}
    if sub.get("name") and sub["name"] not in spec.substitutes:
        sub["name"] = None
        sub["why_it_wins"] = None
    reaction["likely_substitute"] = sub
    reaction["archetype"] = archetype
    return reaction
