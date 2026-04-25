from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import auth, db
from .challenger import (
    MODEL_DEFAULT,
    challenge_pitch,
    improve_pitch_expression,
    is_ready,
    react_as_persona,
)
from .models import ProductSpec
from .personas import ARCHETYPES, generate_personas
from .simulation import run_simulation
from .tracking import build_report

ARCHETYPE_BLURBS = {
    "grinder": "Long attention span, high motivation. Hard to capture, hard to lose. Will keep using what works.",
    "explorer": "Tries everything once. Low loyalty — jumps to whatever feels new and shiny.",
    "burnout": "Short attention, low energy. Drops off fast unless the product respects their bandwidth.",
    "budgeter": "Highly price-sensitive. Free or near-free wins. Will tolerate friction to save money.",
    "social": "Mid-everything, moves with peers. Adoption depends on what their friends use.",
}

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _parse_spec(spec_dict: dict) -> ProductSpec:
    from .models import MechanismScores

    mechanisms = None
    m_raw = spec_dict.get("mechanisms")
    if m_raw is not None:
        mechanisms = MechanismScores(
            R=float(m_raw["R"]),
            U=float(m_raw["U"]),
            W=float(m_raw["W"]),
            F=float(m_raw["F"]),
            M=float(m_raw["M"]),
            strategy=str(m_raw.get("strategy", "balanced")),
        )
    return ProductSpec(
        name=spec_dict["name"],
        category=spec_dict["category"],
        features=list(spec_dict["features"]),
        price_monthly=float(spec_dict["price_monthly"]),
        target_segment=spec_dict["target_segment"],
        substitutes=list(spec_dict.get("substitutes", [])),
        mechanisms=mechanisms,
    )


def _run_simulation(spec: ProductSpec, personas: int, days: int, seed: int) -> dict:
    people = generate_personas(personas, seed=seed)
    result = run_simulation(spec, people, days=days, seed=seed)
    report = build_report(result)
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
    return payload


def _save_run(
    user_id: str, kind: str, product_name: str, spec_id: int | None, result: dict
) -> int:
    with db.get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO saved_runs (user_id, spec_id, kind, product_name, result_json)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, spec_id, kind, product_name, json.dumps(result)),
        ).fetchone()
        return row["id"]


class Handler(BaseHTTPRequestHandler):
    # ---------- response helpers ----------

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404, "Not found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as e:
            self._send_json(400, {"error": f"invalid json: {e}"})
            return None

    # ---------- auth helpers ----------

    def _bearer_token(self) -> str | None:
        header = self.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            return None
        return header[7:].strip() or None

    def _current_user(self) -> dict | None:
        return auth.user_from_bearer(self._bearer_token())

    def _require_auth(self) -> dict | None:
        user = self._current_user()
        if user is None:
            self._send_json(401, {"error": "not authenticated"})
            return None
        return user

    # ---------- GET ----------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            return self._send_file(
                STATIC_DIR / "index.html", "text/html; charset=utf-8"
            )
        if path == "/login":
            return self._send_file(
                STATIC_DIR / "login.html", "text/html; charset=utf-8"
            )
        if path == "/app.js":
            return self._send_file(STATIC_DIR / "app.js", "application/javascript")
        if path == "/login.js":
            return self._send_file(STATIC_DIR / "login.js", "application/javascript")
        if path == "/styles.css":
            return self._send_file(STATIC_DIR / "styles.css", "text/css")
        if path == "/fixture":
            return self._send_file(FIXTURES_DIR / "flashcards.json", "application/json")

        if path == "/config":
            return self._send_json(
                200,
                {
                    "supabase_url": os.environ.get("SUPABASE_URL", ""),
                    "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
                },
            )

        if path == "/auth/me":
            user = self._current_user()
            if user is None:
                return self._send_json(401, {"error": "not authenticated"})
            return self._send_json(
                200,
                {
                    "email": user["email"],
                    "challenger_ready": is_ready(),
                },
            )

        if path == "/agents":
            user = self._require_auth()
            if user is None:
                return
            personas = [
                {
                    "name": name,
                    "blurb": ARCHETYPE_BLURBS.get(name, ""),
                    "params": {k: list(v) for k, v in bands.items()},
                }
                for name, bands in ARCHETYPES.items()
            ]
            critic = {
                "name": "Pitch Challenger",
                "blurb": "Skeptical investor that adversarially critiques your pitch before the simulation runs. Surfaces kill-shots, weak features, pricing risks, and fragile assumptions.",
                "model": MODEL_DEFAULT,
                "ready": is_ready(),
            }
            expression = {
                "name": "Expression Helper",
                "blurb": "Rewrites your draft pitch into sharper founder-ready language without fabricating features, metrics, or traction.",
                "model": MODEL_DEFAULT,
                "ready": is_ready(),
            }
            return self._send_json(
                200,
                {"personas": personas, "critic": critic, "expression": expression},
            )

        if path == "/specs":
            user = self._require_auth()
            if user is None:
                return
            return self._list_specs(user["id"])

        if path == "/runs":
            user = self._require_auth()
            if user is None:
                return
            params = parse_qs(parsed.query)
            limit = int(params.get("limit", ["50"])[0])
            kind = params.get("kind", [None])[0]
            return self._list_runs(user["id"], limit=limit, kind=kind)

        if path.startswith("/runs/"):
            user = self._require_auth()
            if user is None:
                return
            run_id = path[len("/runs/") :]
            return self._get_run(user["id"], run_id)

        self.send_error(404, "Not found")

    # ---------- POST ----------

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._read_json_body()
        if body is None:
            return

        if path == "/simulate":
            user = self._require_auth()
            if user is None:
                return
            return self._simulate(user["id"], body)

        if path == "/challenge":
            user = self._require_auth()
            if user is None:
                return
            return self._challenge(user["id"], body)

        if path == "/express-idea":
            user = self._require_auth()
            if user is None:
                return
            return self._express_idea(user["id"], body)

        if path == "/agents/react":
            user = self._require_auth()
            if user is None:
                return
            return self._persona_react(user["id"], body)

        if path == "/specs":
            user = self._require_auth()
            if user is None:
                return
            return self._save_spec(user["id"], body)

        self.send_error(404, "Not found")

    # ---------- DELETE ----------

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        user = self._require_auth()
        if user is None:
            return

        if path.startswith("/specs/"):
            return self._delete_owned(user["id"], "saved_specs", path[len("/specs/") :])
        if path.startswith("/runs/"):
            return self._delete_owned(user["id"], "saved_runs", path[len("/runs/") :])

        self.send_error(404, "Not found")

    # ---------- simulate / challenge ----------

    def _simulate(self, user_id: str, body: dict) -> None:
        try:
            spec_dict = dict(body["spec"])
            # Accept mechanism scores + strategy from a prior challenge run
            if "mechanism_scores" in body and "mechanisms" not in spec_dict:
                spec_dict["mechanisms"] = {
                    **body["mechanism_scores"],
                    "strategy": body.get("product_strategy", "balanced"),
                }
            spec = _parse_spec(spec_dict)
            report = _run_simulation(
                spec,
                personas=int(body.get("personas", 100)),
                days=int(body.get("days", 30)),
                seed=int(body.get("seed", 42)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            return self._send_json(400, {"error": str(exc)})
        run_id = _save_run(user_id, "simulation", spec.name, None, report)
        report["_run_id"] = run_id
        self._send_json(200, report)

    def _challenge(self, user_id: str, body: dict) -> None:
        try:
            spec = _parse_spec(body["spec"])
        except (KeyError, ValueError, TypeError) as exc:
            return self._send_json(400, {"error": f"invalid spec: {exc}"})

        if not is_ready():
            return self._send_json(
                200,
                {
                    "error": "No AI provider key set. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env."
                },
            )

        try:
            critique = challenge_pitch(
                spec,
                pitch_text=body.get("pitch_text") or None,
                model=body.get("model") or MODEL_DEFAULT,
            )
        except Exception as exc:
            return self._send_json(200, {"error": str(exc)})

        run_id = _save_run(user_id, "challenge", spec.name, None, critique)
        critique["_run_id"] = run_id
        self._send_json(200, critique)

    def _express_idea(self, user_id: str, body: dict) -> None:
        try:
            spec = _parse_spec(body["spec"])
        except (KeyError, ValueError, TypeError) as exc:
            return self._send_json(400, {"error": f"invalid spec: {exc}"})

        if not is_ready():
            return self._send_json(
                200,
                {
                    "error": "No AI provider key set. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env."
                },
            )

        try:
            expression = improve_pitch_expression(
                spec,
                pitch_text=body.get("pitch_text") or None,
                model=body.get("model") or MODEL_DEFAULT,
            )
        except Exception as exc:
            return self._send_json(200, {"error": str(exc)})

        self._send_json(200, expression)

    def _persona_react(self, user_id: str, body: dict) -> None:
        archetype = body.get("archetype")
        if archetype not in ARCHETYPES:
            return self._send_json(400, {"error": "unknown archetype"})

        try:
            spec = _parse_spec(body["spec"])
        except (KeyError, ValueError, TypeError) as exc:
            return self._send_json(400, {"error": f"invalid spec: {exc}"})

        if not is_ready():
            return self._send_json(
                200,
                {
                    "error": "No AI provider key set. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env."
                },
            )

        try:
            reaction = react_as_persona(
                spec,
                archetype=archetype,
                bands=ARCHETYPES[archetype],
                blurb=ARCHETYPE_BLURBS.get(archetype, ""),
                pitch_text=body.get("pitch_text") or None,
                model=body.get("model") or MODEL_DEFAULT,
            )
        except Exception as exc:
            return self._send_json(200, {"error": str(exc)})

        self._send_json(200, reaction)

    # ---------- specs CRUD ----------

    def _list_specs(self, user_id: str) -> None:
        with db.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, spec_json, created_at
                FROM saved_specs
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        specs = [
            {
                "id": row["id"],
                "name": row["name"],
                "spec": row["spec_json"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ]
        self._send_json(200, {"specs": specs})

    def _save_spec(self, user_id: str, body: dict) -> None:
        name = str(body.get("name", "")).strip()
        spec = body.get("spec")
        if not name or not isinstance(spec, dict):
            return self._send_json(400, {"error": "name and spec required"})
        try:
            _parse_spec(spec)
        except (KeyError, ValueError, TypeError) as exc:
            return self._send_json(400, {"error": f"invalid spec: {exc}"})

        with db.get_connection() as conn:
            row = conn.execute(
                """
                INSERT INTO saved_specs (user_id, name, spec_json)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (user_id, name, json.dumps(spec)),
            ).fetchone()
        self._send_json(200, {"id": row["id"]})

    # ---------- runs CRUD ----------

    def _list_runs(self, user_id: str, *, limit: int, kind: str | None) -> None:
        limit = max(1, min(limit, 200))
        with db.get_connection() as conn:
            if kind:
                rows = conn.execute(
                    """
                    SELECT id, kind, product_name, created_at
                    FROM saved_runs
                    WHERE user_id = %s AND kind = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, kind, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, kind, product_name, created_at
                    FROM saved_runs
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                ).fetchall()
        self._send_json(
            200,
            {
                "runs": [
                    {
                        "id": r["id"],
                        "kind": r["kind"],
                        "product_name": r["product_name"],
                        "created_at": r["created_at"].isoformat(),
                    }
                    for r in rows
                ]
            },
        )

    def _get_run(self, user_id: str, run_id_raw: str) -> None:
        try:
            run_id = int(run_id_raw)
        except ValueError:
            return self._send_json(404, {"error": "not found"})
        with db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, kind, product_name, result_json, created_at
                FROM saved_runs
                WHERE id = %s AND user_id = %s
                """,
                (run_id, user_id),
            ).fetchone()
        if row is None:
            return self._send_json(404, {"error": "not found"})
        self._send_json(
            200,
            {
                "id": row["id"],
                "kind": row["kind"],
                "product_name": row["product_name"],
                "result": row["result_json"],
                "created_at": row["created_at"].isoformat(),
            },
        )

    def _delete_owned(self, user_id: str, table: str, id_raw: str) -> None:
        try:
            row_id = int(id_raw)
        except ValueError:
            return self._send_json(404, {"error": "not found"})
        # Table is hardcoded in the caller, not user-supplied.
        with db.get_connection() as conn:
            cur = conn.execute(
                f"DELETE FROM {table} WHERE id = %s AND user_id = %s",
                (row_id, user_id),
            )
            rowcount = cur.rowcount
        if rowcount == 0:
            return self._send_json(404, {"error": "not found"})
        self._send_json(200, {"ok": True})

    # ---------- logging ----------

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.address_string()}] {format % args}")


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"KNE-Guards dashboard → http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    serve(args.host, args.port)
