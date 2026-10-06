# AttackGraph AI

> **Autonomous LLM-Driven Security Analysis & Adaptive Attack Graph Platform**

AttackGraph AI is a research-grade security platform that couples a **Gemini function-calling LLM agent** with real penetration-testing tools to autonomously discover assets, probe for vulnerabilities, construct structured attack graphs, and continuously refine confidence estimates through Bayesian online learning — all within a strict allowlist-enforced scope.

Built across **19 incremental engineering phases**, the system demonstrates how agentic AI can be applied responsibly to security analysis workflows.

---

## Table of Contents

1. [Key Features](#key-features)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Tech Stack](#tech-stack)
5. [Quick Start](#quick-start)
6. [API Reference](#api-reference)
7. [How the Agent Works](#how-the-agent-works)
8. [Confidence & Calibration](#confidence--calibration)
9. [Bayesian Pattern Learning](#bayesian-pattern-learning)
10. [Human Review & Propagation](#human-review--propagation)
11. [Frontend Dashboard](#frontend-dashboard)
12. [Running Tests](#running-tests)
13. [Database Schema](#database-schema)
14. [Project Phases](#project-phases)
15. [Known Limitations](#known-limitations)
16. [License](#license)

---

## Key Features

| Feature | Description |
|---|---|
| 🤖 **Autonomous Agent Loop** | ReAct-style Gemini LLM decision loop that plans and executes security tool calls step-by-step without unconstrained shell access |
| 🔒 **Allowlist-Enforced Scope** | Every tool validates targets against a YAML allowlist — prevents lateral-movement accidents, hardcoded to Juice Shop & DVWA |
| 🕸️ **Attack Graph Construction** | Persistent PostgreSQL-backed graph of nodes (services, endpoints, vulnerabilities, secrets) and typed edges with stated confidence scores |
| 🔁 **Automatic Re-verification** | Any edge can be re-run against the live target; outcomes (VERIFIED / REFUTED) are stored and update the graph deterministically |
| 🧑‍⚖️ **Human Review & Propagation** | Confirm or invalidate any AI-proposed edge via REST API; downstream "undermined" nodes are automatically flagged using truth-maintenance propagation |
| 📊 **Offline Calibration** | ECE (Expected Calibration Error) + Brier score measure whether stated confidence actually matches real-world correctness — with mandatory sample-size warnings |
| 🧠 **Bayesian Pattern Learning** | Laplace-smoothed priors per pattern-key update after every verified/refuted outcome; new edges receive a blended confidence score that adapts over time |
| 🖥️ **Interactive Graph UI** | React + React Flow dashboard with node inspector, human-review buttons, refuted-edge hiding, step replay scrubber, and calibration view |
| 🎬 **Replay Mode** | Chronological reconstruction of how the graph was built, step by step, cross-referenced to agent log entries |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     USER / AUDITOR                          │
└───────────────────────────┬─────────────────────────────────┘
                            │ Browser
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              React + React Flow Dashboard                    │
│  TopBar │ GraphCanvas │ InspectorPanel │ ActivityLog         │
│  ReplayControls │ CalibrationView                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ REST / JSON
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Application Server                  │
│                                                             │
│  /scans          /calibration      /pattern-stats           │
│  /scans/{id}/    /scans/{id}/      /scans/{id}/             │
│   agent/run       calibration       replay                  │
│   graph           critical-node-    agent-log               │
│   edges/*/        analysis          ffuf                    │
│   human-review                      nodes/*/                │
│   reverify                           http-probe             │
│                                      access-control-check   │
│                                      reflected-input-check  │
├────────────────────────┬────────────────────────────────────┤
│   Agent Loop           │         Graph Engine                │
│   agent/loop.py        │  graph/calibration.py              │
│                        │  graph/confidence.py               │
│   • Summarises state   │  graph/critical_node.py            │
│   • Calls Gemini API   │  graph/pattern_learning.py         │
│   • Executes tools     │  graph/propagation.py              │
│   • Logs to agent_log  │  graph/verification.py             │
├────────────────────────┴────────────────────────────────────┤
│                       Tool Layer                            │
│  tools/nmap.py              tools/access_control_check.py   │
│  tools/ffuf.py              tools/reflected_input_check.py  │
│  tools/http_probe.py        tools/secret_detection.py       │
│  tools/envelope.py          (allowlist checked per call)    │
├─────────────────────────────────────────────────────────────┤
│                   Target Environments                        │
│  OWASP Juice Shop (localhost:3000)                          │
│  DVWA (localhost:8080)                                      │
├─────────────────────────────────────────────────────────────┤
│               PostgreSQL Database                            │
│  scans │ nodes │ edges │ evidence                           │
│  agent_log │ human_corrections │ pattern_stats              │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
AttackGraph AI/
├── agent/
│   ├── loop.py              # LLM agent decision loop (ReAct-style)
│   └── state_summary.py     # Scan state summariser for agent context
├── alembic/
│   └── versions/
│       ├── 0001_initial_schema.py
│       ├── 0002_add_edge_fields.py
│       ├── 0003_add_node_is_critical.py
│       ├── 0004_add_node_undermined.py
│       └── 0005_pattern_stats.py
├── api/
│   ├── main.py              # FastAPI app, CORS, router registration
│   ├── schemas.py           # Pydantic request/response models
│   ├── allowlist.py         # Target URL allowlist enforcement
│   └── routes/
│       ├── scans.py         # All scan-scoped endpoints
│       ├── calibration.py   # GET /calibration
│       └── pattern_stats.py # GET /pattern-stats
├── config/
│   └── allowlist.yaml       # Allowed target hosts and ports
├── db/
│   ├── database.py          # SQLAlchemy engine & session factory
│   └── models.py            # ORM models (Scan, Node, Edge, Evidence, ...)
├── docs/
│   ├── FINAL_REPORT.md      # Full project analysis & novelty claims
│   └── end_to_end_run_2026_10_06.md  # Live pipeline execution record
├── frontend/
│   └── src/
│       ├── App.tsx           # Root component, scan selector, overlay routing
│       ├── api/client.ts     # Typed API client functions
│       ├── types/index.ts    # Shared TypeScript interfaces
│       └── components/
│           ├── GraphCanvas.tsx      # React Flow graph renderer
│           ├── InspectorPanel.tsx   # Node/edge detail + human-review
│           ├── ActivityLog.tsx      # Agent step log sidebar
│           ├── ReplayControls.tsx   # Step scrubber
│           ├── CalibrationView.tsx  # ECE/Brier score dashboard
│           ├── TopBar.tsx           # Scan selector + controls
│           └── CustomNodes.tsx      # Node type card renderers
├── graph/
│   ├── calibration.py       # ECE, Brier score computation
│   ├── confidence.py        # Static confidence rationale table
│   ├── critical_node.py     # Bottleneck/critical node analysis
│   ├── pattern_learning.py  # Bayesian prior update & blending
│   ├── propagation.py       # Downstream invalidation propagation
│   └── verification.py      # Automatic edge re-verification
├── tests/                   # 93 tests across 16 modules
├── tools/
│   ├── envelope.py                # Tool output envelope schema
│   ├── nmap.py                    # Nmap port scanner
│   ├── ffuf.py                    # FFUF directory fuzzer
│   ├── http_probe.py              # HTTP body probe + secret detection
│   ├── secret_detection.py        # Regex-based secret pattern matching
│   ├── access_control_check.py    # IDOR/BOLA path/param manipulation
│   └── reflected_input_check.py   # Reflected input context detection
├── wordlists/common.txt     # Wordlist for FFUF discovery
├── docker-compose.yml       # Postgres + Juice Shop + DVWA containers
├── requirements.txt
└── alembic.ini
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM Agent** | Google Gemini (`gemini-2.0-flash` via `google-genai` SDK) |
| **Backend API** | FastAPI + Uvicorn |
| **ORM & Migrations** | SQLAlchemy 2.x + Alembic |
| **Database** | PostgreSQL 16 (Docker) |
| **HTTP Client** | httpx (async-compatible) |
| **Security Tools** | Nmap, FFUF (host binaries), custom Python probes |
| **Frontend** | React 18, TypeScript, Vite, React Flow |
| **Test Framework** | pytest (93 tests, SQLite in-memory fixtures) |
| **Containerisation** | Docker Compose |

---

## Quick Start

### Prerequisites

- **Docker Desktop** running
- **Python 3.11+**
- **Node.js 18+** (for the dashboard)
- **`nmap`** installed on your host
- **`ffuf`** installed on your host (expected at `C:\ffuf\ffuf.EXE` on Windows or `ffuf` on PATH on Linux/Mac)
- A **Gemini API key** from [Google AI Studio](https://aistudio.google.com/)

### 1. Clone & enter the project

```bash
git clone https://github.com/Mudita-Singh/Attackgraph-AI.git
cd Attackgraph-AI
```

### 2. Start target containers

```bash
docker compose up -d
```

Starts:
- `attackgraph-postgres` → PostgreSQL 16 on port **5432**
- `attackgraph-juice-shop` → OWASP Juice Shop on port **3000**
- `attackgraph-dvwa` → DVWA on port **8080**

### 3. Set up Python environment

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://attackgraph_user:attackgraph_pass@localhost:5432/attackgraph_db
```

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Start the backend API

```bash
python -m uvicorn api.main:app --port 8000 --reload
```

API available at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

### 7. Start the frontend dashboard

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at `http://localhost:5173`

---

## API Reference

### Scan Management

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scans` | Create a new scan (target URL is allowlist-checked) |
| `GET` | `/scans` | List all scans with status |
| `GET` | `/scans/{id}` | Get a single scan |

### Agent

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scans/{id}/agent/run` | Run autonomous agent loop. Optional `?max_steps=N` (default 15) |
| `GET` | `/scans/{id}/agent-log` | Retrieve full agent reasoning + action log |
| `GET` | `/scans/{id}/replay` | Chronological graph construction event stream |

### Graph

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/scans/{id}/graph` | Full attack graph (nodes + edges) |
| `GET` | `/scans/{id}/nodes/{node_id}/evidence` | Evidence records for a node |
| `GET` | `/scans/{id}/path-confidence/{node_id}` | All attack paths to node with confidence scores |
| `POST` | `/scans/{id}/critical-node-analysis` | Bottleneck node analysis (disconnection impact ranking) |

### Security Tools

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scans/{id}/nmap` | Nmap port scan |
| `POST` | `/scans/{id}/ffuf` | FFUF directory fuzzing |
| `POST` | `/scans/{id}/nodes/{nid}/http-probe` | HTTP body probe + secret detection |
| `POST` | `/scans/{id}/nodes/{nid}/access-control-check` | IDOR/BOLA identifier-swap test |
| `POST` | `/scans/{id}/nodes/{nid}/reflected-input-check` | Reflected input context analysis |

### Verification & Human Review

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/scans/{id}/edges/{eid}/reverify` | Automatically re-run verification for an edge |
| `POST` | `/scans/{id}/edges/{eid}/human-review` | Record human `confirm` or `refute` decision |

### Calibration & Learning

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/calibration` | Global ECE + Brier score across all scans |
| `GET` | `/scans/{id}/calibration` | Calibration scoped to a single scan |
| `GET` | `/pattern-stats` | All learned Bayesian pattern priors |
| `GET` | `/pattern-stats/{key}` | Prior for one specific pattern key |

---

## How the Agent Works

The agent runs a **ReAct (Reason + Act)** loop:

```
1. Summarise current scan state
   - nodes discovered so far
   - edges created
   - which nodes still have pending checks (http_probe, access_control_check, etc.)
   
2. Send state summary to Gemini API
   - system prompt encodes tool descriptions and security strategy
   - Gemini responds with a function call (tool name + arguments)

3. Validate the chosen action
   - Cross-scan node ownership check (security isolation)
   - Deduplication check (no repeating completed actions)
   - Allowlist enforcement (all tool calls route through scope guard)

4. Execute the tool
   - Results are persisted to the database (nodes, edges, evidence)
   - agent_log entry is written with thought + action + observation

5. Repeat until:
   - Gemini returns no_further_action (all pending checks exhausted)
   - max_steps limit is hit
   - API timeout / 503 (state is saved; loop can be resumed)
```

---

## Confidence & Calibration

Each edge is created with a **stated confidence** score (0.0 – 1.0) derived from a static rationale table (`graph/confidence.py`) and blended with the learned Bayesian prior (see below).

**Calibration** (`graph/calibration.py`) evaluates whether these scores are accurate by comparing them to resolved outcomes:

- `VERIFIED` → 1 (correct)
- `REFUTED` / `HUMAN_INVALIDATED` → 0 (incorrect)

Metrics computed across 5 confidence buckets (0–0.2, 0.2–0.4, 0.4–0.6, 0.6–0.8, 0.8–1.0):

| Metric | Formula |
|---|---|
| **ECE** | $\sum_b \frac{n_b}{N} \|\bar{c}_b - \bar{o}_b\|$ |
| **Brier Score** | $\frac{1}{N} \sum_i (c_i - o_i)^2$ |

Empty buckets report `"observed_rate": null` and `"note": "no data in this range"`. A `sample_size_warning` is always included when N < 30.

---

## Bayesian Pattern Learning

Each security finding pattern (e.g. `access_control_check:same_session_different_identifier`) has a row in the `pattern_stats` table tracking:
- `times_verified` — resolved as correct
- `times_refuted` — resolved as incorrect (REFUTED or HUMAN_INVALIDATED)

**Prior confidence** (Laplace smoothed):
$$\text{prior} = \frac{\text{times\_verified} + 1}{\text{times\_verified} + \text{times\_refuted} + 2}$$

**Blended final confidence** for a new edge:
$$w = \frac{1}{1 + \text{observation\_count}}$$
$$\text{final\_confidence} = w \cdot \text{evidence\_score} + (1 - w) \cdot \text{prior}$$

Both `confidence` (blended) and `evidence_only_confidence` (raw) are stored on each edge for transparency.

**Effect:** A pattern that has been invalidated twice will produce a prior of 0.25 instead of 0.5, automatically lowering the stated confidence on future findings of the same type.

---

## Human Review & Propagation

When a human marks an edge as **invalid** (`refute`):

1. Edge `status` → `human_invalidated`, `verification_outcome` → `HUMAN_INVALIDATED`
2. `pattern_stats.times_refuted` increments for that pattern key
3. Downstream propagation runs (`graph/propagation.py`):
   - All nodes that were **only reachable via this edge** are flagged `undermined = true`
   - Nodes with **alternative supporting paths** are left intact
4. A `HumanCorrection` row is recorded with reviewer name and reason

When a human marks an edge as **valid** (`confirm`):
1. Edge `status` → `verified`, `verification_outcome` → `VERIFIED`
2. `pattern_stats.times_verified` increments

---

## Frontend Dashboard

The React dashboard (`frontend/`) provides:

- **Scan selector** — switch between all scans in the database
- **Graph canvas** — interactive React Flow layout with colour-coded node types:
  - 🟦 Services (ppp_service)
  - 🟩 Endpoints
  - 🟥 Vulnerabilities / findings
  - 🟨 Secrets
- **Edge rendering** — dashed/red for refuted/invalidated, weighted by confidence
- **Inspector panel** — click any node/edge to see evidence, confidence, reasoning, and human-review buttons
- **Activity log** — scrollable agent reasoning and action log
- **Show/hide refuted edges** toggle
- **Replay mode** — scrub through graph construction step by step
- **Calibration view** — ECE, Brier score, per-bucket bar chart, global vs scan-scoped selector

---

## Running Tests

```bash
python -m pytest -v
```

**93 tests across 16 modules — all passing.**

| Module | What it tests |
|---|---|
| `test_scans.py` | Scan CRUD, allowlist enforcement, bypass edge cases |
| `test_nmap.py` | Nmap tool against live containers + missing binary |
| `test_ffuf.py` | FFUF tool against Juice Shop + DVWA + missing binary |
| `test_http_probe.py` | HTTP probe + secret detection against real containers |
| `test_secret_detection.py` | Regex pattern matching, clean response handling |
| `test_access_control_check.py` | IDOR detection, path/param identifier swapping, cross-scan scoping |
| `test_reflected_input_check.py` | Reflection context classification, unencoded/encoded/not-reflected |
| `test_agent_loop.py` | Loop termination, dedup, max_steps, cross-scan isolation, API error handling |
| `test_graph_api.py` | Graph endpoint, evidence, path confidence |
| `test_path_confidence.py` | Weakest-link path scoring, disconnected path errors |
| `test_propagation.py` | Multi-path undermining, single-path undermining, API integration |
| `test_critical_node.py` | Bottleneck ranking, tie-breaking, idempotency |
| `test_verification.py` | Reverification, human review confirm/refute, cross-scan scoping |
| `test_calibration.py` | ECE/Brier hand-verified values, empty bucket format, API routes |
| `test_pattern_learning.py` | Prior worked examples (Section 34.6), blend math, counter increments, integration |
| `test_replay.py` | Replay event ordering, step attribution, null step handling |

---

## Database Schema

```
scans
  id, target_url, status, created_at, updated_at

nodes
  id, scan_id, label, node_type, is_critical, undermined, properties, created_at

edges
  id, scan_id, source_node_id, target_node_id, relation_type, pattern_key,
  confidence, evidence_only_confidence, status, verification_outcome,
  reasoning, step, properties, created_at

evidence
  id, scan_id, node_id, edge_id, tool_name, raw_output, parsed_findings, timestamp

agent_log
  id, scan_id, step_number, thought, action, observation, timestamp

human_corrections
  id, scan_id, target_type, target_id, correction_type, notes, created_at

pattern_stats
  pattern_key (PK), times_verified, times_refuted, last_updated
```

---

## Project Phases

| Phases | What was built |
|---|---|
| **1 – 3** | Target allowlist, scan management API, tool output envelope |
| **4 – 6** | Nmap port scanner, FFUF directory fuzzer, HTTP secret detection |
| **7 – 8** | IDOR/BOLA access control probe, reflected-input context analyser |
| **9** | Autonomous Gemini agent loop with function calling |
| **10 – 12** | PostgreSQL graph schema, confidence rationale table, automatic re-verification |
| **13 – 14** | Downstream invalidation propagation, critical bottleneck node analysis |
| **15 – 16** | React + React Flow graph dashboard, replay scrubber endpoint |
| **17 – 18** | Offline calibration (ECE/Brier), Bayesian adaptive pattern confidence |
| **19** | End-to-end pipeline run record, final documentation |

Full detail: [`docs/FINAL_REPORT.md`](docs/FINAL_REPORT.md)  
Live run record: [`docs/end_to_end_run_2026_10_06.md`](docs/end_to_end_run_2026_10_06.md)

---

## Known Limitations

- **LLM API availability:** Gemini endpoint occasionally returns 503 under load. The agent loop records the failure in `agent_log` and preserves state — re-running `POST /agent/run` resumes from where it left off.
- **Unauthenticated scans:** Access-control checks against `/rest/basket/1` and `/api/Users/1` on Juice Shop return 401 without a session token. The tool correctly reports no finding; authenticated scanning requires passing `session_cookies` or `auth_token` to the tool.
- **Calibration sample size:** With < 30 resolved edges, ECE and Brier scores are illustrative only. The `sample_size_warning` field in all calibration responses makes this explicit.
- **Pattern learning cold start:** `pattern_stats` is intentionally not backfilled from historical test fixture edges (which have ambiguous repeated outcomes). Learning accumulates from live resolutions going forward.
- **Target scope:** The allowlist currently permits only `localhost:3000` (Juice Shop) and `localhost:8080` (DVWA). Adding new targets requires editing `config/allowlist.yaml`.

---

## License

MIT
