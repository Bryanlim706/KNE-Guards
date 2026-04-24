from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .models import ProductSpec
from .personas import generate_personas
from .simulation import run_simulation
from .tracking import Report, build_report


def _load_spec(path: Path) -> ProductSpec:
    from .models import MechanismScores
    data = json.loads(path.read_text())
    mechanisms = None
    if "mechanisms" in data:
        m = data["mechanisms"]
        mechanisms = MechanismScores(
            R=float(m["R"]), U=float(m["U"]), W=float(m["W"]),
            F=float(m["F"]), M=float(m["M"]),
            strategy=str(m.get("strategy", "balanced")),
        )
    return ProductSpec(
        name=data["name"],
        category=data["category"],
        features=list(data["features"]),
        price_monthly=float(data["price_monthly"]),
        target_segment=data["target_segment"],
        substitutes=list(data.get("substitutes", [])),
        mechanisms=mechanisms,
    )


def _render(report: Report) -> str:
    lines = []
    lines.append(f"=== Viability Report: {report.product_name} ===")
    lines.append(f"Personas simulated: {report.n_personas}   Days: {report.days}")
    lines.append("")
    lines.append(f"Adoption rate:   {report.adoption_rate:.1%}")
    lines.append(f"Abandoned:       {report.abandoned_rate:.1%}")
    lines.append(f"Switched away:   {report.switched_rate:.1%}")
    lines.append(
        f"Viability score: {report.viability_score:.2f}   (0 = flop, 1 = sticky)"
    )
    lines.append("")
    lines.append("Retention curve (active on each day):")
    step = max(1, len(report.retention_curve) // 10)
    for d in range(0, len(report.retention_curve), step):
        bar = "█" * int(report.retention_curve[d] * 30)
        lines.append(f"  Day {d:>2}: {report.retention_curve[d]:5.1%} {bar}")
    lines.append("")
    lines.append("By archetype:")
    for arch, counts in sorted(report.persona_breakdown.items()):
        lines.append(
            f"  {arch:<10} retained={counts['retained']:<3} abandoned={counts['abandoned']:<3} switched={counts['switched']:<3} (n={counts['total']})"
        )
    if report.switched_to:
        lines.append("")
        lines.append("Switched to:")
        for sub, n in sorted(report.switched_to.items(), key=lambda x: -x[1]):
            lines.append(f"  {sub}: {n}")
    if report.drop_off_by_day:
        lines.append("")
        lines.append("Drop-off days (top 5):")
        for day, n in sorted(report.drop_off_by_day.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  Day {day}: {n}")
    if report.survivability_score is not None:
        ms = report.mechanism_scores
        lines.append("")
        lines.append(
            f"Survivability score: {report.survivability_score:.2f}   "
            f"Decision: {report.decision}   Strategy: {report.mechanism_scores.get('strategy', 'balanced')}"
        )
        lines.append(
            f"Mechanisms:  R={ms['R']:.2f}  U={ms['U']:.2f}  W={ms['W']:.2f}"
            f"  F={ms['F']:.2f}  F'={ms['F_prime']:.2f}  M={ms['M']:.2f}"
        )
        if report.bottlenecks:
            parts = []
            for arch, dims in report.bottlenecks.items():
                parts.append(f"{arch}({','.join(dims)})")
            lines.append(f"Active killers: {' '.join(parts)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KNE-Guards: simulate student product adoption"
    )
    parser.add_argument("spec", type=Path, help="Path to product spec JSON")
    parser.add_argument(
        "--personas",
        type=int,
        default=100,
        help="Number of persona agents (default 100)",
    )
    parser.add_argument(
        "--days", type=int, default=30, help="Simulation horizon in days (default 30)"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    parser.add_argument(
        "--json", action="store_true", help="Emit raw JSON report instead of text"
    )
    args = parser.parse_args(argv)

    product = _load_spec(args.spec)
    personas = generate_personas(args.personas, seed=args.seed)
    result = run_simulation(product, personas, days=args.days, seed=args.seed)
    report = build_report(result)

    if args.json:
        payload = {
            "product_name": report.product_name,
            "days": report.days,
            "n_personas": report.n_personas,
            "adoption_rate": report.adoption_rate,
            "abandoned_rate": report.abandoned_rate,
            "switched_rate": report.switched_rate,
            "viability_score": report.viability_score,
            "retention_curve": report.retention_curve,
            "persona_breakdown": report.persona_breakdown,
            "switched_to": report.switched_to,
            "drop_off_by_day": report.drop_off_by_day,
        }
        if report.survivability_score is not None:
            payload["mechanism_scores"] = report.mechanism_scores
            payload["archetype_survivability"] = report.archetype_survivability
            payload["bottlenecks"] = report.bottlenecks
            payload["survivability_score"] = report.survivability_score
            payload["decision"] = report.decision
        print(json.dumps(payload, indent=2))
    else:
        print(_render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
