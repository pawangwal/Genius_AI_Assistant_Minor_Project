# Genius AI Assistant Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver 6 targeted improvements to the existing Genius AI Assistant: Chat with File Upload, Get-Cricket-Scores integration, Voice Transcription lifecycle bugfix, Dashboard Temperature removal & real Network status, and Demo Tasks/Reminders with notifications, while preserving the existing modular architecture, UI design, and security boundaries.

**Architecture:** Extend FastAPI backend with dedicated modular endpoints for cricket scores, file text extraction, provider health, and demo seeding; update React/TypeScript frontend with ChatPanel, CricketScoresWidget, real provider polling in SystemStatusCards, fixed MediaRecorder state machine, and in-app NotificationToasts.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Zustand, FastAPI, Pydantic v2, PostgreSQL 16 (asyncpg + SQLAlchemy), pypdf, httpx, faster-whisper.

**Spec:** User request specifying 6 targeted improvements, verification requirements, and zero regression constraint.

## Global Constraints
- Preserve existing React, TypeScript, Vite, FastAPI, PostgreSQL, scikit-learn IPL pipeline, and Faster-Whisper implementations.
- No microservices, Kafka, Redis, vector databases, or heavy RAG frameworks.
- Zero hardcoded secrets; keep `CRICAPI_KEY` and LLM keys strictly on backend; never expose keys in API responses or logs.
- Strict type-checking (`tsc --noEmit`), linting, and full backend test passing with dedicated test database isolation.

---

### Task 1: Fix Voice Transcription Lifecycle Bug

**Files:**
- Modify: `src/services/audioRecorder.ts`
- Modify: `src/components/CommandConsole.tsx:75-125`
- Test: `backend/tests/test_stt.py`

**Interfaces:**
- `AudioRecorderService.getState(): 'idle' | 'recording' | 'processing' | 'error'`
- `AudioRecorderService.startRecording(): Promise<void>` (guards against double start)
- `AudioRecorderService.stopRecording(): Promise<Blob | null>` (returns null or rejects safely if inactive, never throws unexpected exception on unstarted recorder)

- [ ] **Step 1: Inspect and fix `AudioRecorderService` in `src/services/audioRecorder.ts`**
Add explicit recorder state machine:
```typescript
export type RecorderState = 'idle' | 'recording' | 'processing' | 'error';
```
Ensure `stopRecording` checks state, handles inactive recorder safely, stops all media tracks upon stop or cancel, and tracks errors.

- [ ] **Step 2: Fix `CommandConsole.tsx` lifecycle bug**
Replace the unconstrained `useEffect([isListening])` that calls `recorderRef.current.stopRecording()` on initial mount when `isListening` is false.
Introduce `wasListeningRef` or an explicit toggle handler so `stopRecording()` is only triggered if recording was actually active.
Disable stop control until `recorder.getState() === 'recording'`.

- [ ] **Step 3: Run TypeScript type check**
Run: `npx tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 4: Run existing STT backend tests**
Run: `.venv/Scripts/python -m pytest backend/tests/test_stt.py -v`
Expected: All tests PASS.

---

### Task 2: Remove Temperature Card & Implement Real Network Status

**Files:**
- Modify: `backend/app/api/v1/health.py`
- Modify: `backend/tests/test_health.py`
- Modify: `src/components/SystemStatusCards.tsx`
- Modify: `src/services/api.ts`

**Interfaces:**
- `GET /api/v1/health/network`: returns `{ fastapi: "online", provider: string, status: "connected" | "checking" | "degraded" | "offline", detail: string, model: string }`
- `fetchNetworkStatus(): Promise<NetworkStatusResponse>` in `src/services/api.ts`

- [ ] **Step 1: Write backend tests for `/health/network`**
In `backend/tests/test_health.py`, add test verifying `/api/v1/health/network` reports active provider, reachable state, and masks credentials.

- [ ] **Step 2: Implement `/health/network` endpoint in `backend/app/api/v1/health.py`**
Inspect active provider via `settings.LLM_PROVIDER`:
- If `ollama`: call `ollama_provider.check_health()`
- If `openrouter`: call `openrouter_provider.check_availability(force_refresh=False)`
Return safe status without leaking headers or keys.

- [ ] **Step 3: Update `SystemStatusCards.tsx`**
- Remove `Thermometer` import, `temperature` state, and Temperature `StatusCard`.
- Reflow grid from `grid-cols-2 md:grid-cols-3 lg:grid-cols-5` to `grid-cols-2 md:grid-cols-4 lg:grid-cols-4`.
- Replace `Math.random() > 0.05` simulated network with polling `fetchNetworkStatus()` every 10 seconds.
- Display `Connected` (green), `Checking` (cyan), `Degraded` (amber), `Offline` (red) with explanatory tooltip and sublabel indicating active model/provider.

- [ ] **Step 4: Verify with pytest & tsc**
Run: `.venv/Scripts/python -m pytest backend/tests/test_health.py -v`
Run: `npx tsc --noEmit`
Expected: PASS.

---

### Task 3: Integrate CricAPI Cricket Scores

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/core/config.py`
- Create: `backend/app/api/v1/cricket.py`
- Modify: `backend/app/api/v1/router.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_cricket.py`
- Create: `src/components/CricketScoresWidget.tsx`
- Modify: `src/components/NavigationSidebar.tsx`
- Modify: `src/services/api.ts`

**Interfaces:**
- `GET /api/v1/cricket/scores` (and alias `GET /api/cricket/scores`)
- Returns `{ status: "success" | "empty" | "unconfigured" | "error", message?: string, matches: CricketMatch[] }`
- Each match contains: `id, name, teams, match_type, scores, status, venue, date, match_ended`
- `CricketScoresWidget`: compact horizontal ticker/bar placed directly above IPL Predictor sidebar item.

- [ ] **Step 1: Add `CRICAPI_KEY` to `config.py`**
In `backend/app/core/config.py`, add `CRICAPI_KEY: Optional[str] = Field(default=None)` and mask in `sanitize_for_logging()`.

- [ ] **Step 2: Write tests in `backend/tests/test_cricket.py`**
Test missing key, CricAPI success response parsing, HTTP error handling, and timeout handling.

- [ ] **Step 3: Implement `backend/app/api/v1/cricket.py` and register in `router.py` and `main.py`**
Fetch `https://api.cricapi.com/v1/currentMatches?apikey={key}&offset=0` with 10s timeout. Extract only needed fields, handle errors without exposing key.

- [ ] **Step 4: Create `src/components/CricketScoresWidget.tsx` and integrate in `NavigationSidebar.tsx`**
Render compact cards directly above IPL Predictor with team names, scores, overs, status, manual refresh button, loading state, empty state, and auto-refresh without overlapping requests.

- [ ] **Step 5: Verify tests and TypeScript**
Run: `.venv/Scripts/python -m pytest backend/tests/test_cricket.py -v`
Run: `npx tsc --noEmit`

---

### Task 4: Add Chat Option With File Upload (.txt, .md, .csv, .json, .pdf)

**Files:**
- Modify: `backend/requirements.txt` (add `pypdf>=5.0.0`)
- Create: `backend/app/services/file_extractor.py`
- Create: `backend/tests/test_file_extractor.py`
- Modify: `backend/app/api/v1/chat.py`
- Create: `src/components/panels/ChatPanel.tsx`
- Modify: `src/components/NavigationSidebar.tsx`
- Modify: `src/components/MainInterface.tsx`
- Modify: `src/services/api.ts`

**Interfaces:**
- `POST /api/v1/chat/upload`: multipart `file`, validates extension & max 5MB size, extracts text, returns `{ filename, content_type, size_bytes, char_count, extracted_text }`
- `POST /api/v1/chat/completions`: accepts messages with extracted file context and streams SSE tokens.
- `ChatPanel`: dark background, cyan accents, purple message bubbles, file picker with badge, size display, remove button, normal text chat & streaming.

- [ ] **Step 1: Write tests in `backend/tests/test_file_extractor.py`**
Test extraction of `.txt`, `.md`, `.json`, `.csv`, `.pdf`, rejection of `.exe` / oversized / empty files.

- [ ] **Step 2: Implement `backend/app/services/file_extractor.py`**
Pure python extractor for text, markdown, json, csv, and pdf via `pypdf`. Enforce 5MB limit and character bounding.

- [ ] **Step 3: Add `POST /api/v1/chat/upload` in `backend/app/api/v1/chat.py`**
Add upload endpoint returning extracted text.

- [ ] **Step 4: Implement `src/components/panels/ChatPanel.tsx`**
Build Chat UI with file attachment button, selected file badge (name, size, remove button), SSE token streaming, and Genius branding.

- [ ] **Step 5: Add Chat nav item in `NavigationSidebar.tsx` and route in `MainInterface.tsx`**
Place Chat between Home and Tasks.

- [ ] **Step 6: Verify backend tests and frontend type check**
Run: `.venv/Scripts/python -m pytest backend/tests/test_file_extractor.py -v`
Run: `npx tsc --noEmit`

---

### Task 5: Add Demo Tasks, Reminders, and In-App Notifications

**Files:**
- Create: `scripts/seed_demo_data.py`
- Modify: `backend/app/main.py`
- Create: `src/components/NotificationToast.tsx`
- Modify: `src/App.tsx`
- Modify: `src/components/panels/TasksPanel.tsx`
- Modify: `src/components/panels/RemindersPanel.tsx`

**Interfaces:**
- Idempotent seed function creating ~3 tasks and ~2 reminders for `local-user` in dev profile.
- `NotificationToast`: displays in-app toast alerts on task completion, reminder dismissal, and when reminder becomes due.
- Due reminder checker running on 10s interval avoiding duplicate alerts via tracked ID set.

- [ ] **Step 1: Implement idempotent seeding in `scripts/seed_demo_data.py` and `backend/app/main.py`**
Seed:
1. Task: "Review IPL match prediction analytics report" (General)
2. Task: "Calibrate local microphone input levels" (System)
3. Task: "Audit PostgreSQL persistence test isolation" (Security)
4. Reminder: "Genius AI Assistant Project Walkthrough" (Due today)
5. Reminder: "Evaluate live cricket scores sync status" (Due tomorrow)
Only seed if `count == 0` for `local-user` and `APP_ENV != "production"`.

- [ ] **Step 2: Implement `NotificationToast.tsx` and mount in `App.tsx`**
Create toast provider/container supporting `success`, `info`, `warning`, `alarm`.

- [ ] **Step 3: Connect Tasks & Reminders actions to toasts**
Trigger toasts on task toggle/completion, reminder dismissal, and when polling finds a reminder whose `due_time <= now`.

- [ ] **Step 4: Verify persistence and notifications**
Run: `.venv/Scripts/python scripts/seed_demo_data.py`
Run: `npx tsc --noEmit`

---

### Task 6: Documentation & Complete Verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

- [ ] **Step 1: Update `README.md`**
Document OpenRouter default vs. local Ollama option. Clarify offline vs. online capabilities (IPL ML, STT, PG are offline; OpenRouter & CricAPI require internet). Document `CRICAPI_KEY`.

- [ ] **Step 2: Update `.env.example`**
Add `CRICAPI_KEY=your_cricapi_key_here`.

- [ ] **Step 3: Run full backend test suite with test database**
Run: `.venv/Scripts/python -m pytest backend/tests -v`
Confirm 100% pass rate.

- [ ] **Step 4: Run frontend production build**
Run: `npm run build`
Confirm 0 build errors.

- [ ] **Step 5: Run release packager**
Run: `.venv/Scripts/python scripts/package_release.py`
Confirm clean release archive generated.
