# KNE-Guards

**AI-powered product validation platform for student-focused startups.**

KNE-Guards lets founders stress-test a product idea before building it. Submit a pitch, get an adversarial AI critique, then watch 100 synthetic students decide whether to adopt, stick with, or abandon your product — day by day, over 30 days.

---

## What It Does

Most startup validation is optimistic. KNE-Guards is not.

The platform combines two layers of evaluation:

**1. Pitch Challenger**
An LLM-driven skeptical investor tears apart your pitch. It surfaces kill shots, challenges your assumptions feature by feature, scores how well your product replaces existing behaviour, and tells you which substitutes will beat you and why.

**2. Behavioural Simulation**
100 synthetic student personas — Grinders, Explorers, Burnouts, Budgeters, and Socials — each make daily decisions about whether to keep using your product. The simulation tracks adoption rates, retention curves, churn days, and which competing tools win market share. At the end, a survivability score tells you whether to build, test further, or drop the idea.

---

## Student Persona Archetypes

| Archetype | Behaviour |
|-----------|-----------|
| **Grinder** | High motivation, long attention span. Hard to acquire, hard to lose. |
| **Explorer** | Tries everything once. Low loyalty, jumps to whatever feels new. |
| **Burnout** | Low energy. Drops off fast unless the product respects their bandwidth. |
| **Budgeter** | Highly price-sensitive. Free or near-free wins every time. |
| **Social** | Moves with peers. Adoption depends on what their friends use. |

---

## Mechanism Scores

The challenger scores five structural dimensions of your product (0.0 – 1.0):

| Score | Meaning |
|-------|---------|
| **R** | Replacement — how strongly does this displace an existing behaviour? |
| **U** | Usage frequency — how often does the product give users a reason to return? |
| **W** | Workflow integration — how embedded is this in existing routines? |
| **F** | Discoverability — how strong is organic inflow? |
| **M** | Word-of-mouth — how likely are users to recommend this to peers? |

These scores feed directly into the simulation and survivability analysis.

---

## Tech Stack

- **Backend** — Python (stdlib HTTP server, no framework)
- **AI** — OpenAI GPT-4o (primary), Anthropic Claude (fallback)
- **Auth & Database** — Supabase (PostgreSQL + JWT auth)
- **Frontend** — Vanilla JS / HTML / CSS

---

## Installation

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier works)
- An [OpenAI](https://platform.openai.com) API key

### 1. Clone the repository

```bash
git clone https://github.com/Bryanlim706/KNE-Guards.git
cd KNE-Guards
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
# OpenAI — get a key at https://platform.openai.com/
OPENAI_API_KEY=your_openai_api_key

# Supabase — found at: Dashboard → Settings → API
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_anon_public_key
SUPABASE_JWT_SECRET=your_jwt_secret

# Supabase — found at: Dashboard → Settings → Database → Transaction pooler URI
SUPABASE_DB_URL=postgresql://postgres.your-project-id:your-password@aws-region.pooler.supabase.com:6543/postgres
```

**Where to find each value in Supabase:**

| Variable | Location |
|----------|----------|
| `SUPABASE_URL` | Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Settings → API → Project API keys → `anon public` |
| `SUPABASE_JWT_SECRET` | Settings → API → JWT Settings → JWT Secret (click Reveal) |
| `SUPABASE_DB_URL` | Settings → Database → Connection string → Transaction pooler |

### 4. Run the server

```bash
python -m kne_guards.server
```

The dashboard will be available at **http://127.0.0.1:8000**

---

## Usage

1. **Sign up** for an account on the login page
2. **Enter your product spec** — name, category, price, target segment, features, and known substitutes
3. **Run the Pitch Challenger** to get an adversarial AI critique with kill shots and mechanism scores
4. **Run the Simulation** to see how 100 student personas adopt and retain (or abandon) your product over 30 days
5. **Review the survivability report** — Build, Test, or Drop

---

## Project Structure

```
kne_guards/
├── server.py         # HTTP API and request routing
├── challenger.py     # LLM pitch critique and persona reactions
├── simulation.py     # Multi-agent daily decision simulation
├── personas.py       # Student archetype definitions and generation
├── decisions.py      # Per-day decision logic and satisfaction tracking
├── tracking.py       # Retention curves, viability scores, reports
├── survivability.py  # Mechanism scoring and survivability analysis
├── models.py         # Data models (ProductSpec, Persona, etc.)
├── auth.py           # JWT authentication
└── db.py             # Supabase database connectivity
static/
├── index.html        # Main dashboard
├── app.js            # Frontend logic
└── styles.css        # Styling
```
