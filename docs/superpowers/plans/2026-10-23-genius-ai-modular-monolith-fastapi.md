# Genius AI Assistant - Production-Grade Architecture & Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Genius AI Assistant into a secure, production-ready, local-first multimodal assistant featuring a FastAPI modular monolith, offline scikit-learn IPL win prediction inference, bounded native LLM tool execution powered by local Ollama, browser audio capture with local Whisper STT, PostgreSQL persistence with ownership boundaries, and full Docker/CI verification.

**Architecture:** A clean modular monolith built in `backend/app/` with strict layered separation (`api/v1`, `core`, `ml`, `tools`, `services`, `models`), an async PostgreSQL persistence layer with explicit non-fallback error semantics, native tool-calling loop communicating exclusively with local Ollama, local `faster-whisper` speech transcription, and browser `MediaRecorder` audio capture updating the React/Tailwind/Zustand interface.

**Tech Stack:**
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn, scikit-learn, pandas, SQLAlchemy (asyncio) + asyncpg, alembic, httpx, faster-whisper
- **AI & ML:** Local Ollama (`OLLAMA_CHAT_MODEL`), scikit-learn Logistic Regression Pipeline (`pipe.pkl`), local Whisper STT
- **Frontend:** React 18, TypeScript, Vite, Zustand, Tailwind CSS, Web Audio API / MediaRecorder, Browser SpeechSynthesis
- **Infra & DevOps:** Docker, Docker Compose, PostgreSQL 16, GitHub Actions CI, Pytest

---

## Global Constraints & Principles

1. **Local-First & Data Routing Privacy:** Zero data egress to third-party AI APIs (no OpenRouter, no Google Gemini, no cloud speech APIs). All LLM inference runs via local Ollama; all transcription runs via local Whisper.
2. **No Silent Database Fallback:** If PostgreSQL is unreachable, `/api/v1/health/ready` fails (HTTP 503) and persistence-dependent routes (`/tasks`, `/reminders`) return HTTP 503 Service Unavailable. Never silently swallow database failures with in-memory stores.
3. **Authoritative ML Model (`pipe.pkl`):** The authoritative artifact is `pipe.pkl`. Preprocessing, feature names, and class ordering must be verified from the artifact and notebook prior to API serving.
4. **Execution Safety:** Zero host-level shell execution (`os.system` / `subprocess`). Zero host browser launches (`webbrowser.open`). Application/search navigation must return structured URL payloads to the client.
5. **Bounded Agent Execution:** The Ollama tool-calling loop enforces `max_iterations=5`, per-request timeout (30s), JSON Schema argument validation with Pydantic, and sanitized tool outputs.
6. **Two Security Profiles:**
   - **Profile A (Local Development):** Bound to `127.0.0.1`, strict CORS for local frontend, auth optional only while bounded locally.
   - **Profile B (Public Deployment):** Mandatory authentication, authorization on tasks/reminders, TLS, rate limiting, and network isolation for Ollama and PostgreSQL.

---

## Mathematical Specification for IPL Inference

For a 20-over run chase:
- Inputs:
  - `batting_team: str`, `bowling_team: str`, `city: str`
  - `target_score: int > 0`
  - `current_score: int >= 0`
  - `overs_completed: int >= 0 and <= 20` (full completed overs)
  - `balls_in_over: int >= 0 and <= 5` (additional balls bowled in current over)
  - `wickets_out: int >= 0 and <= 10`
- Derived features:
  - `legal_balls_bowled = (overs_completed * 6) + balls_in_over`
  - `balls_left = max(0, 120 - legal_balls_bowled)`
  - `runs_left = max(0, target_score - current_score)`
  - `wickets_left = max(0, 10 - wickets_out)`
  - `crr = (current_score / (legal_balls_bowled / 6.0))` if `legal_balls_bowled > 0` else `0.0`
  - `rrr = (runs_left * 6.0 / balls_left)` if `balls_left > 0` else `(999.0 if runs_left > 0 else 0.0)`
  - `total_runs_x = target_score`
- Exact DataFrame column alignment required by pipeline:
  `['batting_team', 'bowling_team', 'city', 'runs_left', 'balls_left', 'wickets_left', 'total_runs_x', 'crr', 'rrr']`
- Output:
  - Returns `batting_win_probability` and `bowling_win_probability` (summing to 1.0) and `projected_winner`.
  - **No arbitrary confidence labels** — return calibrated probabilities and raw match context.

---

## File Structure & Module Map

```
Genius_AI_Assistant_Minor_Project/
├── .env.example                               # Validated environment template
├── .gitignore                                 # Hardened git ignore (.env, *.pkl, venv)
├── docker-compose.yml                         # Local orchestrated services (app + postgres + ollama)
├── backend/
│   ├── Dockerfile                             # Multi-stage production python container
│   ├── requirements.txt                       # Pinned production dependencies
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                            # FastAPI app, lifespan, CORS, middleware
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                      # Pydantic Settings (Ollama, DB, STT, Auth)
│   │   │   ├── database.py                    # Async engine, sessionmaker, readiness probe
│   │   │   └── security.py                    # Auth dependencies, token validation, ownership
│   │   ├── ml/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py                     # IPL MatchInput, PredictionOutput models
│   │   │   ├── ipl_pipeline.py                # pipe.pkl loader, derived feature calculator, inference
│   │   │   └── evaluation.py                  # Evaluation metrics & consistency test suite
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── entities.py                    # Task, Reminder, User SQLAlchemy models
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py                     # Tool schemas (predict_ipl, create_task, etc.)
│   │   │   ├── registry.py                    # Validated tool dispatcher
│   │   │   └── handlers.py                    # Tool handler logic
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ollama_provider.py             # Local Ollama client adapter with error normalization
│   │   │   ├── agent.py                       # Bounded tool-calling loop + SSE streamer
│   │   │   └── stt.py                         # Local faster-whisper STT service
│   │   └── api/
│   │       ├── __init__.py
│   │       └── v1/
│   │           ├── __init__.py
│   │           ├── router.py                  # Aggregated router
│   │           ├── health.py                  # Liveness and readiness probes
│   │           ├── predictions.py             # POST /predictions/ipl
│   │           ├── tasks.py                   # GET, POST, PATCH, DELETE /tasks (with ownership)
│   │           ├── reminders.py               # GET, POST, DELETE /reminders (with ownership)
│   │           ├── chat.py                    # POST /chat/completions (SSE streaming via Ollama)
│   │           └── stt.py                     # POST /stt (multipart audio upload to faster-whisper)
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                        # Fixtures (client, mock db, test model)
│       ├── test_health.py                     # Liveness and readiness tests
│       ├── test_ipl_inference.py              # IPL mathematical semantics & prediction tests
│       ├── test_persistence.py               # Task/reminder CRUD and ownership enforcement
│       ├── test_tools.py                      # Tool registry and argument validation
│       ├── test_agent_loop.py                 # Ollama tool-calling loop, bounds, errors
│       ├── test_stt.py                        # Audio upload validation & transcription
│       └── test_security.py                   # Profile A/B security gate tests
├── src/                                       # Preserved React frontend
│   ├── services/
│   │   ├── api.ts                             # Typed client for backend /api/v1
│   │   └── audioRecorder.ts                   # Browser MediaRecorder audio capture
│   ├── components/
│   │   ├── CommandConsole.tsx                 # SSE chat + local STT audio upload + client TTS
│   │   └── panels/
│   │       ├── IPLPredictorPanel.tsx          # Real API prediction call + validation
│   │       ├── TasksPanel.tsx                 # Backend API CRUD wiring
│   │       └── RemindersPanel.tsx             # Backend API CRUD wiring
```

---

## Detailed Implementation Tasks (Ordered)

### Phase 1: Security Baseline & Artifact Verification
- **Task 1.1: Secrets and Git Conflict Remediation**
  - Files: `.gitignore`, `.env.example`, `config.py`, remove `test_gemini_api.py`
  - Actions: Delete `test_gemini_api.py` containing exposed key; resolve uncommitted merge conflict by discarding `pipe3.pkl` reference and retaining `pipe.pkl`; ensure `.gitignore` excludes `.env`, `*.pkl`, `__pycache__`, `.venv`.
  - Acceptance Criteria: Zero hardcoded secrets; no unresolved merge conflicts.
- **Task 1.2: Deep ML Artifact Inspection**
  - Script/Action: Write verification script to inspect `pipe.pkl`: feature order, transformer steps, one-hot encoder categories, class labels, and scikit-learn version.
  - Acceptance Criteria: Feature order and class mapping documented explicitly in `backend/app/ml/schemas.py`.

### Phase 2: FastAPI Foundation, Settings & Health Probes
- **Task 2.1: Project Scaffolding & Pydantic Settings**
  - Files: `backend/requirements.txt`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/main.py`.
  - Settings: `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `DATABASE_URL`, `STT_MODEL_PATH`, `AUTH_REQUIRED`, `CORS_ORIGINS`.
- **Task 2.2: Versioned Router & Health Probes**
  - Files: `backend/app/api/v1/health.py`, `backend/tests/test_health.py`.
  - Liveness (`/health/live`): 200 OK unconditionally.
  - Readiness (`/health/ready`): Checks PostgreSQL connection, Ollama availability, and ML model loaded. Returns 503 if any downstream component is unready.
  - Acceptance Criteria: Unreachable database reports `{"database": "unreachable"}` with HTTP 503; startup fails if invalid configuration is passed.

### Phase 3: Real IPL Inference & Frontend Integration
- **Task 3.1: IPL Feature Engineering & Prediction Service**
  - Files: `backend/app/ml/schemas.py`, `backend/app/ml/ipl_pipeline.py`, `backend/app/api/v1/predictions.py`, `backend/tests/test_ipl_inference.py`.
  - Logic: Validate match state, calculate `runs_left`, `balls_left`, `wickets_left`, `crr`, `rrr` using the exact mathematical specification. Handle zero-ball, targets reached, and 20-over boundaries.
  - Acceptance Criteria: Probabilities sum to 1.0; returns projected winner and probabilities without arbitrary confidence labels; comprehensive test suite passes.
- **Task 3.2: Connect IPLPredictorPanel to Backend**
  - Files: `src/services/api.ts`, `src/components/panels/IPLPredictorPanel.tsx`.
  - Actions: Replace `Math.random()` simulation with `POST /api/v1/predictions/ipl`. Add inputs for current score, overs bowled, wickets fallen, and target. Display animated win probability meters and error handling.
  - Acceptance Criteria: Real prediction received and rendered; UI type-checks cleanly with Vite.

### Phase 4: PostgreSQL Persistence & Ownership Model
- **Task 4.1: Database Models & Migrations**
  - Files: `backend/app/models/entities.py`, `backend/app/core/database.py`.
  - Entities: `TaskEntity`, `ReminderEntity`, `UserEntity`.
  - Ownership: Support user-level ownership (`user_id`). In Profile A (local dev), default to local user. In Profile B, require authenticated session.
- **Task 4.2: Tasks & Reminders API Routes**
  - Files: `backend/app/api/v1/tasks.py`, `backend/app/api/v1/reminders.py`, `backend/tests/test_persistence.py`.
  - Actions: CRUD endpoints. If DB is unavailable, return HTTP 503 with structured error (NO silent fallback).
  - Modify `src/components/panels/TasksPanel.tsx` and `RemindersPanel.tsx` to sync with backend.
  - Acceptance Criteria: Tasks/reminders survive backend restarts; unauthorized cross-user mutations rejected.

### Phase 5: Local Ollama Provider & Bounded Tool-Calling Loop
- **Task 5.1: Ollama Client Adapter & Error Normalization**
  - Files: `backend/app/services/ollama_provider.py`.
  - Actions: Wrap Ollama API (`/api/chat`) using `httpx` with timeout (30s) and error normalization.
- **Task 5.2: Tool Registry & Handlers**
  - Files: `backend/app/tools/schemas.py`, `backend/app/tools/handlers.py`, `backend/app/tools/registry.py`, `backend/tests/test_tools.py`.
  - Tools: `predict_ipl_match`, `create_task`, `list_tasks`, `create_reminder`, `list_reminders`, `search_web` (client navigation URL payload only).
- **Task 5.3: Bounded Agent Orchestrator & SSE Streaming**
  - Files: `backend/app/services/agent.py`, `backend/app/api/v1/chat.py`, `backend/tests/test_agent_loop.py`.
  - Constraints: `max_iterations=5`, strict JSON Schema validation, Hindi/English multilingual prompt. Yields SSE events (`tool_call`, `tool_result`, `token`, `done`, `error`).
  - Acceptance Criteria: Agent answers questions and invokes tools locally via Ollama; stops at max iterations; zero cloud API calls.

### Phase 6: Local STT & Frontend Voice Integration
- **Task 6.1: Local Faster-Whisper Transcription Service**
  - Files: `backend/app/services/stt.py`, `backend/app/api/v1/stt.py`, `backend/tests/test_stt.py`.
  - Logic: Accept multipart audio (`audio/webm`, `audio/wav`), validate size (<=10MB) and duration (<=120s), transcribe locally with `faster-whisper`.
- **Task 6.2: Frontend MediaRecorder & CommandConsole**
  - Files: `src/services/audioRecorder.ts`, `src/components/CommandConsole.tsx`.
  - Actions: Record audio in browser via `MediaRecorder`; upload to `/api/v1/stt`; feed transcript to SSE chat endpoint; render live tokens; speak response via browser `SpeechSynthesis`.
  - Acceptance Criteria: Complete audio workflow runs locally with zero external network dependencies; server microphone code eliminated.

### Phase 7: End-to-End Tests, Security Verification & Observability
- **Files:** `backend/tests/test_security.py`, `backend/tests/test_e2e.py`.
- **Actions:** Test offline operation (external network disabled), profile validation (Profile A vs Profile B), rate limits, and structured error reporting.
- **Acceptance Criteria:** Full test suite passes; linter (`ruff`) passes.

### Phase 8: Docker Compose, CI Pipeline & Release Gate
- **Files:** `backend/Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `README.md`.
- **Cleanup:** Delete deprecated `server.py` and `server.js`.
- **Documentation:** Architecture diagrams, setup instructions for Ollama and PostgreSQL, performance metrics.
- **Acceptance Criteria:** `docker compose config` valid; CI passes all checks; production release gate verified.
