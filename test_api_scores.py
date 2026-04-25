"""
Tests the live challenge_pitch API against known products.
Compares AI-assigned mechanism scores to expected decisions.
Run with: python3 test_api_scores.py
"""
from __future__ import annotations

from kne_guards.challenger import challenge_pitch
from kne_guards.models import ProductSpec
from kne_guards.survivability import compute_survivability, MechanismScores

TESTS = [
    # ── CLEAR BUILDS ────────────────────────────────────────────────────────
    dict(
        name="WhatsApp", expected="Build",
        spec=ProductSpec(
            name="WhatsApp", category="messaging", price_monthly=0,
            target_segment="university students",
            features=["instant messaging", "voice calls", "group chats", "status updates", "file sharing"],
            substitutes=["SMS", "iMessage", "Instagram DMs", "Telegram"],
        ),
    ),
    dict(
        name="Duolingo", expected="Build",
        spec=ProductSpec(
            name="Duolingo", category="language learning", price_monthly=0,
            target_segment="university students learning a second language",
            features=["daily streaks", "gamified lessons", "push notifications", "leaderboards", "XP system"],
            substitutes=["Rosetta Stone", "language classes", "YouTube tutorials", "Babbel"],
        ),
    ),
    dict(
        name="Discord", expected="Build",
        spec=ProductSpec(
            name="Discord", category="communication", price_monthly=0,
            target_segment="university students",
            features=["voice channels", "text channels", "server communities", "screen sharing", "roles and permissions"],
            substitutes=["WhatsApp", "Slack", "Microsoft Teams", "Skype"],
        ),
    ),
    dict(
        name="Figma", expected="Build",
        spec=ProductSpec(
            name="Figma", category="design tool", price_monthly=0,
            target_segment="design and CS students",
            features=["real-time collaboration", "prototyping", "component libraries", "auto-layout", "browser-based"],
            substitutes=["Adobe XD", "Sketch", "Canva", "PowerPoint"],
        ),
    ),
    dict(
        name="Notion", expected="Build",
        spec=ProductSpec(
            name="Notion", category="productivity", price_monthly=0,
            target_segment="university students",
            features=["notes", "databases", "kanban boards", "templates", "team wikis"],
            substitutes=["Google Docs", "Evernote", "Roam Research", "OneNote"],
        ),
    ),
    dict(
        name="Quizlet", expected="Build",
        spec=ProductSpec(
            name="Quizlet", category="study tool", price_monthly=0,
            target_segment="university students",
            features=["flashcard creation", "learn mode", "practice tests", "shared decks", "match game"],
            substitutes=["Anki", "paper flashcards", "Brainly", "Chegg"],
        ),
    ),
    dict(
        name="ChatGPT", expected="Build",
        spec=ProductSpec(
            name="ChatGPT", category="AI assistant", price_monthly=0,
            target_segment="university students",
            features=["essay help", "code debugging", "concept explanation", "summarisation", "Q&A"],
            substitutes=["Google Search", "Stack Overflow", "tutors", "Wolfram Alpha"],
        ),
    ),

    # ── CLEAR DROPS ─────────────────────────────────────────────────────────
    dict(
        name="Google+", expected="Drop",
        spec=ProductSpec(
            name="Google+", category="social network", price_monthly=0,
            target_segment="university students",
            features=["circles", "hangouts", "stream", "communities", "Google integration"],
            substitutes=["Facebook", "Twitter", "Instagram", "Snapchat"],
        ),
    ),
    dict(
        name="Quibi", expected="Drop",
        spec=ProductSpec(
            name="Quibi", category="short-form video", price_monthly=4.99,
            target_segment="university students",
            features=["10-minute episodes", "mobile-only", "premium content", "quick bites format"],
            substitutes=["TikTok", "YouTube Shorts", "Instagram Reels", "Netflix"],
        ),
    ),
    dict(
        name="Google Wave", expected="Drop",
        spec=ProductSpec(
            name="Google Wave", category="collaboration", price_monthly=0,
            target_segment="university students",
            features=["real-time document editing", "inline replies", "drag and drop", "playback"],
            substitutes=["Google Docs", "email", "Slack", "Notion"],
        ),
    ),
    dict(
        name="Evernote", expected="Drop",
        spec=ProductSpec(
            name="Evernote", category="note-taking", price_monthly=10.99,
            target_segment="university students",
            features=["note clipping", "notebooks", "tags", "search", "cross-device sync"],
            substitutes=["Notion", "Apple Notes", "Google Keep", "OneNote"],
        ),
    ),
    dict(
        name="Generic Flashcard App", expected="Drop",
        spec=ProductSpec(
            name="StudyFlash", category="flashcard app", price_monthly=2.99,
            target_segment="university students",
            features=["create flashcards", "flip cards", "basic quiz mode"],
            substitutes=["Anki", "Quizlet", "paper flashcards"],
        ),
    ),

    # ── AMBIGUOUS / TEST ────────────────────────────────────────────────────
    dict(
        name="Clubhouse", expected="Test",
        spec=ProductSpec(
            name="Clubhouse", category="social audio", price_monthly=0,
            target_segment="university students",
            features=["live audio rooms", "drop-in listening", "follow speakers", "raise hand", "invite-only access"],
            substitutes=["podcasts", "Twitter Spaces", "Discord stage channels"],
        ),
    ),
    dict(
        name="BeReal", expected="Test",
        spec=ProductSpec(
            name="BeReal", category="social media", price_monthly=0,
            target_segment="university students",
            features=["daily photo prompt", "dual camera", "friends feed", "no filters", "reactions"],
            substitutes=["Instagram", "Snapchat", "TikTok"],
        ),
    ),
    dict(
        name="Chegg", expected="Test",
        spec=ProductSpec(
            name="Chegg", category="homework help", price_monthly=15.95,
            target_segment="university students",
            features=["textbook solutions", "expert Q&A", "tutoring", "writing help", "practice problems"],
            substitutes=["ChatGPT", "Brainly", "library tutors", "YouTube"],
        ),
    ),
    dict(
        name="Microsoft Teams", expected="Test",
        spec=ProductSpec(
            name="Microsoft Teams", category="communication", price_monthly=0,
            target_segment="university students",
            features=["group chat", "video calls", "assignment submission", "file sharing", "university integration"],
            substitutes=["Discord", "WhatsApp", "Zoom", "Google Classroom"],
        ),
    ),
    dict(
        name="Forest App", expected="Test",
        spec=ProductSpec(
            name="Forest", category="focus app", price_monthly=0,
            target_segment="university students",
            features=["focus timer", "virtual tree growing", "phone lock", "forest statistics", "friend planting"],
            substitutes=["Pomodoro timer", "phone settings", "self-discipline", "Cold Turkey"],
        ),
    ),
]


def run() -> None:
    passed = 0
    failed = 0

    print(f"\n{'Product':<26} {'Expected':<10} {'Got':<10} "
          f"{'R':>5} {'U':>5} {'W':>5} {'F':>5} {'M':>5}  "
          f"{'Score':>6}  {'Strategy':<12}  Result")
    print("─" * 110)

    for t in TESTS:
        try:
            critique = challenge_pitch(t["spec"])
            ms = critique.get("mechanism_scores", {})
            strategy = critique.get("product_strategy", "balanced")
            scores = MechanismScores(
                R=ms.get("R", 0), U=ms.get("U", 0), W=ms.get("W", 0),
                F=ms.get("F", 0), M=ms.get("M", 0), strategy=strategy,
            )
            result = compute_survivability(scores, strategy=strategy)
            match = result.decision == t["expected"]
            symbol = "✓" if match else "✗"
            if match:
                passed += 1
            else:
                failed += 1
            print(
                f"{t['name']:<26} {t['expected']:<10} {result.decision:<10} "
                f"{ms.get('R', 0):>5.2f} {ms.get('U', 0):>5.2f} {ms.get('W', 0):>5.2f} "
                f"{ms.get('F', 0):>5.2f} {ms.get('M', 0):>5.2f}  "
                f"{result.S_aggregate:>6.3f}  {strategy:<12}  {symbol}"
            )
        except Exception as e:
            failed += 1
            print(f"{t['name']:<26} ERROR: {e}")

    total = passed + failed
    print(f"\n{passed}/{total} passed  ({100 * passed // total}% accuracy)")
    print()


if __name__ == "__main__":
    run()
