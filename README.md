# Eutelsat GenAI — Test Case Generator

AI-powered test case generation tool built for the **Eutelsat Release 1 BSS/OSS project**.
Generates ~35 comprehensive test cases per query using a 4-agent agentic pipeline backed by NVIDIA NIM.

---

## Features

| Feature | Description |
|---|---|
| 🤖 **4-Agent Pipeline** | Scout → Generator → Reviewer → Evaluator agents working in sequence |
| ⚡ **Smart Caching** | Exact + fuzzy semantic matching — skips the LLM for similar queries |
| 📊 **Quality Metrics** | Confidence score + hallucination risk per test case |
| 💬 **Follow-up Chat** | Ask the AI to refine, add, or explain test cases after generation |
| 📋 **Jira Integration** | Import test cases as Stories to your project backlog (config-ready) |
| 📥 **Excel Export** | Styled `.xlsx` download with priority colour coding |
| 🗂 **Shared History** | SQLite DB — all sessions visible to everyone on the team |

---

## Tech Stack

- **Backend** — Python, FastAPI, SQLAlchemy, SQLite
- **AI** — NVIDIA NIM API (`openai/gpt-oss-20b` via OpenAI-compatible endpoint)
- **Frontend** — Vanilla JS, custom CSS (no build step, no Node.js required)
- **Export** — openpyxl

---

## Modules Covered (Eutelsat Release 1)

- Order Management
- Billing / Charging
- Contract Management
- Product Catalog
- Customer Management
- Provisioning / Activation
- Reporting / Analytics

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/praveenkarthick108-arch/Eutelsat.git
cd Eutelsat
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your API key

Create a `.env` file in the project root:

```
NVIDIA_API_KEY=your_nvidia_api_key_here
```

> Get your key from [build.nvidia.com](https://build.nvidia.com)

### 4. Run the server

```bash
python main.py
```

Server starts at `http://0.0.0.0:8000`

### 5. Open in browser

```
http://localhost:8000
```

Team members can access it on the same network at:

```
http://<your-machine-ip>:8000
```

---

## How the AI Pipeline Works

```
User Input
    │
    ▼
┌─────────────┐
│ Scout Agent │  Identifies 7 distinct test scenario areas for the feature
└──────┬──────┘
       │
       ▼
┌───────────────────┐
│ Generator Agent   │  Creates 5 test cases per area (~35 total)
│ (×7 areas)        │  Each with description, steps, expected result
└─────────┬─────────┘
          │
          ▼
┌──────────────────┐
│ Reviewer Agent   │  Assigns priority (High / Medium / Low) to all cases
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Evaluator Agent  │  Scores confidence (0–100%) + hallucination risk
└────────┬─────────┘
         │
         ▼
    ~35 Test Cases
    saved to SQLite
```

---

## Semantic Cache

Every generated session is indexed by a hash of `module + feature title + test type`.

On the next request:
1. **Exact match** — same query returns instantly from cache
2. **Fuzzy match** — ≥70% word overlap treated as the same query (Jaccard similarity)
3. **Cache miss** — runs the full pipeline, stores result for 7 days

---

## Project Structure

```
eutelsat-testgen/
├── main.py              # FastAPI app + startup DB migrations
├── ai_pipeline.py       # 4-agent pipeline + follow-up agent
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response schemas
├── database.py          # SQLite engine + session dependency
├── scope_data.py        # Release 1 module/feature reference data
├── requirements.txt
├── .env                 # API key (not committed)
├── routes/
│   ├── generate.py      # POST /api/generate  (cache check + pipeline)
│   ├── sessions.py      # GET  /api/sessions
│   ├── testcases.py     # PUT  /api/testcases/{id}
│   ├── followup.py      # POST /api/sessions/{id}/followup
│   ├── export.py        # GET  /api/export/{id}  (.xlsx download)
│   ├── jira.py          # GET/POST /api/jira/config + /api/jira/import
│   └── scope.py         # GET  /api/scope
└── static/
    └── index.html       # Single-page frontend (vanilla JS)
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Frontend UI |
| `POST` | `/api/generate` | Run pipeline, return test cases |
| `GET` | `/api/sessions` | All saved sessions |
| `GET` | `/api/sessions/{id}` | Single session with test cases |
| `PUT` | `/api/testcases/{id}` | Edit a test case |
| `POST` | `/api/sessions/{id}/followup` | Follow-up chat |
| `GET` | `/api/export/{id}` | Download `.xlsx` |
| `GET/POST` | `/api/jira/config` | Read / save Jira credentials |
| `POST` | `/api/jira/import/{id}` | Generate Jira import preview |

---

## Jira Integration Setup

1. Go to **Settings** in the sidebar
2. Enter your Jira instance URL, project key, email, and API token
3. Generate your API token at [id.atlassian.com](https://id.atlassian.com) → Security → API tokens
4. Click **Import to Jira** on any session — test cases are created as Stories in your backlog, unassigned and status "To Do"

---

## Requirements

```
fastapi==0.111.0
uvicorn==0.30.1
openai==1.35.0
httpx>=0.27.1
sqlalchemy==2.0.31
openpyxl==3.1.4
python-dotenv==1.0.1
```

Python 3.10+ recommended.

---

## Notes

- The SQLite database (`eutelsat_testgen.db`) is created automatically on first run
- The `.env` file is excluded from version control — never commit your API key
- The server uses `reload_excludes` to prevent restarts when the DB is written during generation
- For corporate networks with SSL inspection, the NVIDIA API client uses `httpx` with `verify=False`

---

*Built for the Eutelsat Release 1 QA team — Prodapt*
