"""
Validates the survivability model against real-world products.
Scores are manually assigned based on known product characteristics.
The model should broadly agree with real-world outcomes.
"""
from __future__ import annotations
from kne_guards.models import MechanismScores
from kne_guards.survivability import compute_survivability

PRODUCTS = [
    # ── SUCCESSFUL ──────────────────────────────────────────────────────────
    {
        "name": "WhatsApp",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.85, U=0.90, W=0.70, F=0.50, M=0.95, strategy="viral"),
        # Replaced SMS entirely (R), daily messages (U), deep in routine (W),
        # spreads through contacts (M high), organic via network effects (F moderate)
    },
    {
        "name": "Notion",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.75, U=0.65, W=0.90, F=0.55, M=0.60, strategy="workflow"),
        # Replaces docs/wikis (R), daily use (U), deeply embedded in teams (W),
        # grows via word-of-mouth and templates (M moderate), good SEO/organic (F)
    },
    {
        "name": "Duolingo",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.60, U=0.85, W=0.40, F=0.65, M=0.70, strategy="content"),
        # Habit-forming streaks (U very high), moderate replacement of classes (R),
        # viral notifications + social shame (M), strong organic discovery (F)
    },
    {
        "name": "Spotify",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.90, U=0.95, W=0.60, F=0.60, M=0.65, strategy="content"),
        # Completely replaced CD/iTunes purchasing (R), used daily (U),
        # playlist lock-in (W moderate), strong word-of-mouth (M), organic (F)
    },
    # ── FAILED / STRUGGLED ──────────────────────────────────────────────────
    {
        "name": "Google+",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.20, U=0.35, W=0.15, F=0.40, M=0.25, strategy="viral"),
        # Didn't replace Facebook meaningfully (R low), no reason to return daily (U),
        # nobody's friends were there (M low), forced adoption via Google (F moderate)
    },
    {
        "name": "Quibi",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.25, U=0.40, W=0.20, F=0.30, M=0.15, strategy="content"),
        # Didn't replace anything — competing with YouTube/TikTok for same format (R low),
        # content wasn't compelling enough to return daily (U low),
        # no social sharing mechanic (M very low), poor organic discovery (F)
    },
    {
        "name": "Generic Flashcard App",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.30, U=0.45, W=0.25, F=0.20, M=0.20, strategy="replacement"),
        # Anki already exists for free (R low), used only near exams (U low),
        # not embedded in study workflow (W), no discovery vector (F low), no virality (M)
    },
    {
        "name": "Clubhouse (peak)",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.40, U=0.50, W=0.20, F=0.35, M=0.90, strategy="viral"),
        # Extreme viral growth (M very high), but low replacement of existing behaviour (R),
        # couldn't build daily habit (U moderate), no workflow integration (W),
        # exclusivity created artificial F but didn't sustain
    },
    {
        "name": "Anki",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.80, U=0.70, W=0.55, F=0.45, M=0.30, strategy="replacement"),
        # Strongly replaces paper flashcards + rote study (R), spaced repetition = daily use (U),
        # becomes part of study routine (W moderate), low virality (M) but strong word-of-mouth in med/law
    },
    {
        "name": "BeReal",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.30, U=0.55, W=0.15, F=0.25, M=0.75, strategy="viral"),
        # High initial virality (M), daily notification creates return (U moderate),
        # but didn't replace Instagram meaningfully (R low), no workflow embedding (W),
        # novelty wore off — no structural stickiness
    },
    # ── ADDITIONAL CASES ────────────────────────────────────────────────────
    {
        "name": "TikTok",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.80, U=0.95, W=0.35, F=0.70, M=0.85, strategy="content"),
        # Fully displaced passive entertainment (R), infinite scroll = daily hours (U),
        # algorithm-driven discovery = strong organic (F), extreme virality via shares (M),
        # W moderate — habit loop replaces workflow integration
    },
    {
        "name": "Slack",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.85, U=0.85, W=0.95, F=0.55, M=0.55, strategy="workflow"),
        # Replaced email for internal comms (R), messages all day (U), deeply embedded (W),
        # spreads team-to-team (M moderate), good organic/SEO (F)
    },
    {
        "name": "Vine",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.35, U=0.55, W=0.10, F=0.40, M=0.80, strategy="content"),
        # Strong virality (M) but 6-second format couldn't sustain daily return (U moderate),
        # didn't meaningfully replace anything (R low), no workflow embedding (W),
        # killed when Instagram Stories launched — no structural moat
    },
    {
        "name": "Snapchat",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.60, U=0.80, W=0.35, F=0.40, M=0.80, strategy="viral"),
        # Replaced texting for a generation (R moderate), streaks drove daily use (U),
        # strong viral pull through contacts (M), moderate organic (F),
        # W moderate — not deeply embedded but habit-loop via streaks
    },
    {
        "name": "Google Wave",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.45, U=0.30, W=0.35, F=0.20, M=0.30, strategy="workflow"),
        # Tried to replace email (R moderate) but was too confusing to use daily (U low),
        # workflow embedding never happened because adoption failed (W moderate on paper),
        # low organic discovery (F), nobody invited friends enthusiastically (M)
    },
    {
        "name": "Strava",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.70, U=0.75, W=0.50, F=0.50, M=0.65, strategy="viral"),
        # Replaced fitness logging spreadsheets/Garmin (R), weekly activity drives return (U),
        # becomes the record of your athletic life — hard to leave (W moderate),
        # athletes share runs = strong WOM (M), good SEO for running communities (F)
    },

    # ── STUDENT-SPECIFIC CASES ───────────────────────────────────────────────
    {
        "name": "Grammarly",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.70, U=0.75, W=0.85, F=0.60, M=0.50, strategy="workflow"),
        # Replaces manual proofreading (R), used every time students write (U),
        # embedded in browser/docs = hard to remove (W high), strong organic search (F),
        # moderate WOM — people mention it but don't evangelize (M)
    },
    {
        "name": "Chegg",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.55, U=0.50, W=0.40, F=0.45, M=0.30, strategy="content"),
        # Replaces textbooks and tutoring partially (R moderate), used around exams not daily (U),
        # subscription fatigue + free alternatives eroding it (W low),
        # declining organic due to AI alternatives (F), low WOM — stigma around cheating (M)
    },
    {
        "name": "Roam Research",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.50, U=0.55, W=0.45, F=0.25, M=0.40, strategy="workflow"),
        # Steep learning curve killed student adoption (W lower than expected),
        # replaced by Notion/Obsidian which are simpler (R moderate),
        # niche evangelist community but not broad (M moderate),
        # poor organic discovery — no SEO play (F low)
    },
    {
        "name": "Kahoot",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.65, U=0.45, W=0.70, F=0.55, M=0.60, strategy="workflow"),
        # Replaced paper quizzes in classrooms (R), not used daily — only in class (U low),
        # deeply embedded in teacher workflows = sticky (W high),
        # teachers share it with other teachers (M moderate), good organic via education channels (F)
    },
    {
        "name": "Forest App",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.35, U=0.50, W=0.30, F=0.35, M=0.45, strategy="replacement"),
        # Replaces willpower — weak substitute for actual habit change (R low),
        # used in study sessions but not daily (U moderate),
        # novelty wears off after a few weeks (W low),
        # moderate WOM among productivity-focused students (M)
    },
    {
        "name": "ChatGPT (student use)",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.90, U=0.90, W=0.80, F=0.75, M=0.80, strategy="replacement"),
        # Replaced Google search, Stack Overflow, tutors (R very high),
        # used multiple times daily for essays/code/explanations (U very high),
        # embedded in every academic workflow (W high),
        # massive organic and viral spread (F and M both high)
    },
    {
        "name": "Coursera",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.45, U=0.35, W=0.30, F=0.55, M=0.30, strategy="content"),
        # Partially replaced self-study books (R moderate), but completion rates are <10% (U low),
        # not embedded in daily habit — course fatigue is real (W low),
        # good SEO/organic discovery (F), low WOM — nobody brags about half-finished courses (M)
    },

    # ── ADDITIONAL STUDENT CASES ─────────────────────────────────────────────
    {
        "name": "Discord",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.75, U=0.90, W=0.70, F=0.55, M=0.85, strategy="viral"),
        # Replaced group chats, Skype, and study group emails (R), open all day (U),
        # server structure embeds it in study groups and clubs (W),
        # strong peer recruitment — your study group drags you in (M high)
    },
    {
        "name": "Quizlet",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.75, U=0.60, W=0.55, F=0.65, M=0.55, strategy="replacement"),
        # Replaced paper flashcards and Anki for mainstream students (R),
        # used before every exam but not daily (U moderate),
        # embedded in class study routines (W moderate),
        # strong SEO — students find it searching for subject + flashcards (F),
        # classmates share decks = moderate WOM (M)
    },
    {
        "name": "Evernote",
        "outcome": "FAILURE",
        "m": MechanismScores(R=0.50, U=0.40, W=0.45, F=0.40, M=0.20, strategy="workflow"),
        # Once promising but Notion ate its lunch (R declining),
        # bloated app with slow performance killed daily habit (U),
        # nobody recommends it anymore (M very low),
        # organic declining as Notion dominates searches (F)
    },
    {
        "name": "Obsidian",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.65, U=0.65, W=0.75, F=0.40, M=0.55, strategy="workflow"),
        # Replaces Notion/Roam for students who want local-first notes (R moderate),
        # daily writing habit for power users (U), deeply embedded via vault structure (W),
        # low mainstream discovery — found via Reddit/YouTube rabbit holes (F),
        # passionate niche advocates but not broad WOM (M)
    },
    {
        "name": "Photomath",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.80, U=0.65, W=0.50, F=0.70, M=0.60, strategy="replacement"),
        # Replaced calculator + manual working for homework (R high),
        # used whenever students hit a math problem (U moderate-high),
        # fits naturally into homework flow (W moderate),
        # students share it — especially in high school (M moderate),
        # strong organic via app store searches (F)
    },
    {
        "name": "Google Classroom",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.70, U=0.70, W=0.90, F=0.45, M=0.20, strategy="workflow"),
        # Replaced email-based assignment submission and LMS tools (R),
        # students open it every school day for assignments (U),
        # mandated by schools = extreme workflow embedding (W very high),
        # low WOM — students don't choose it, schools impose it (M low),
        # discovery via institution not organic (F moderate)
    },
    {
        "name": "Figma",
        "outcome": "SUCCESS",
        "m": MechanismScores(R=0.85, U=0.80, W=0.90, F=0.60, M=0.70, strategy="workflow"),
        # Killed Sketch and Adobe XD for design students (R high),
        # used daily in design courses and side projects (U),
        # real-time collaboration embeds it in every group project (W very high),
        # design students evangelize it heavily (M), strong organic via design communities (F)
    },
    {
        "name": "Todoist",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.40, U=0.50, W=0.35, F=0.45, M=0.25, strategy="replacement"),
        # Competes with phone reminders, Notes app, and paper — weak replacement (R),
        # opened when students remember to, not habitual (U moderate),
        # sits outside actual study flow — a separate app to maintain (W low),
        # low WOM — productivity tools are personal and not shared (M)
    },
    {
        "name": "Wolfram Alpha",
        "outcome": "SUCCESS (niche)",
        "m": MechanismScores(R=0.70, U=0.55, W=0.50, F=0.65, M=0.40, strategy="discovery"),
        # Replaces textbook worked examples for STEM students (R moderate-high),
        # used around problem sets, not daily (U moderate),
        # fits STEM homework workflow naturally (W moderate),
        # strong organic via search — students find it searching equations (F),
        # recommended within STEM communities but not broad (M)
    },
    {
        "name": "Brainly",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.45, U=0.45, W=0.30, F=0.60, M=0.30, strategy="content"),
        # Competes with Google search and ChatGPT for homework answers (R declining fast),
        # used around deadlines not daily (U moderate),
        # not embedded in any workflow — pure lookup tool (W low),
        # decent SEO but losing to AI tools (F moderate),
        # low WOM — students don't brag about copying answers (M)
    },
    {
        "name": "Microsoft Teams (student)",
        "outcome": "MIXED",
        "m": MechanismScores(R=0.55, U=0.60, W=0.65, F=0.25, M=0.15, strategy="workflow"),
        # Replaced email for class comms but resented by students (R moderate),
        # used because mandated not by choice (U moderate),
        # forced into workflow by institutions — sticky but not loved (W),
        # no organic discovery — imposed top-down (F low),
        # nobody recommends it to peers (M very low)
    },
]


def run() -> None:
    col_w = 24
    print(f"\n{'Product':<{col_w}} {'Outcome':<16} {'Strategy':<12} "
          f"{'R':>5} {'U':>5} {'W':>5} {'F':>5} {'M':>5}  "
          f"{'Score':>6}  {'Decision':<8}  {'Active Killers'}")
    print("─" * 115)

    for p in PRODUCTS:
        m = p["m"]
        r = compute_survivability(m, strategy=m.strategy)

        killers: list[str] = []
        for arch, dims in r.active_killers.items():
            for d in dims:
                entry = f"{arch[:3]}:{d}"
                if entry not in killers:
                    killers.append(entry)
        killer_str = "  ".join(killers) if killers else "none"

        print(
            f"{p['name']:<{col_w}} {p['outcome']:<16} {m.strategy:<12} "
            f"{m.R:>5.2f} {m.U:>5.2f} {m.W:>5.2f} {m.F:>5.2f} {m.M:>5.2f}  "
            f"{r.S_aggregate:>6.3f}  {r.decision:<8}  {killer_str}"
        )

    print()
    print("Archetype breakdown for a selected product (Clubhouse):")
    clubhouse = next(p for p in PRODUCTS if "Clubhouse" in p["name"])
    r = compute_survivability(clubhouse["m"], strategy=clubhouse["m"].strategy)
    for arch, surv in r.archetype_survivability.items():
        killers = f"  killers={surv.active_killers}" if surv.active_killers else ""
        print(f"  {arch:<10}  S_a={surv.S_a:.3f}{killers}")


if __name__ == "__main__":
    run()
