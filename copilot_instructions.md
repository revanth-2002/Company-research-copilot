# Copilot Instructions

Use this file as the first-stop project guide before reading the full repository.

## Project Summary

This is a full-stack AI research copilot for preparing sellers and business teams for account meetings.

- Backend: FastAPI app in `backend/app`
- Workflow: LangGraph state machine in `backend/app/workflow/graph.py`
- Persistence: SQLite through `backend/app/db.py`
- Frontend: React 19 + TypeScript + Vite app in `frontend/src`
- Main user flow: create a research session, run a multi-node research workflow, persist progress/report, then ask follow-up chat questions grounded in the generated report

## Key Files

- `README.md`: setup, feature overview, and API list
- `architecture.md`: system flow, components, data model, and upgrade path
- `engineering-decisions.md`: rationale and known technical debt
- `backend/app/main.py`: FastAPI routes, SSE event stream, session/chat API boundary
- `backend/app/models.py`: Pydantic request/response schemas
- `backend/app/db.py`: SQLite connection, table setup, session/progress/chat persistence
- `backend/app/config.py`: environment-driven settings
- `backend/app/events.py`: in-memory session event subscriptions for SSE
- `backend/app/workflow/graph.py`: LangGraph nodes, routing, report generation, follow-up answer logic
- `frontend/src/main.tsx`: single-file React app, API calls, SSE subscription, report and chat UI
- `frontend/src/styles.css`: app styling

Ignore generated/local runtime files unless specifically relevant:

- `research_copilot.db`
- `frontend/node_modules`
- Python virtual environments
- `backend/app/config.py.bak`
- `backend/app/config.py.__tmp__`

## Local Commands

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Build frontend:

```bash
cd frontend
npm run build
```

There is no committed automated test suite yet. For verification, at minimum run the backend server, run `npm run build`, create a session through the UI, confirm workflow progress updates, and confirm follow-up chat works after report generation.

## Environment

Backend settings are defined in `backend/app/config.py`.

- `DATABASE_URL`: defaults to `sqlite:///./research_copilot.db`
- `GEMINI_API_KEY`: optional; without it the app should rely on deterministic fallback behavior
- `GEMINI_MODEL`: defaults in code
- `CORS_ORIGINS`: comma-separated frontend origins

Frontend API base URL:

- `frontend/src/main.tsx` uses `VITE_API_URL`
- If unset, it currently defaults to `http://localhost:8001`
- `README.md` says the backend runs on `http://localhost:8000`

When changing API wiring, keep the README, frontend default, and CORS settings aligned.

## Backend Architecture

FastAPI routes in `backend/app/main.py`:

- `GET /health`
- `POST /sessions`
- `GET /sessions`
- `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/events`
- `POST /sessions/{session_id}/run`
- `POST /sessions/{session_id}/chat`

Keep route response shapes compatible with the Pydantic models in `backend/app/models.py` and the TypeScript types in `frontend/src/main.tsx`.

SQLite persistence in `backend/app/db.py` stores JSON fields as text:

- `progress`
- `report`
- `errors`
- `chat`

Use the existing helpers (`create_session`, `get_session`, `update_session`, `append_progress`, `append_chat`) instead of opening new database connections elsewhere.

## Workflow Architecture

The LangGraph workflow lives in `backend/app/workflow/graph.py`.

Current graph nodes:

1. `planner`
2. `research`
3. `synthesis`
4. `quality_check`
5. `report_generation`

The frontend progress UI expects these workflow step names:

- `planner`
- `research`
- `analysis`
- `quality_check`
- `report_generation`

Be careful when renaming graph nodes or progress event node names. The graph currently registers the analysis function as `synthesis`, while the UI labels a step named `analysis`; changes here should keep progress percentages and status text accurate.

The final report shape expected by the frontend is:

```ts
{
  title: string;
  objective: string;
  quality_score: number;
  sections: Record<string, string | string[] | { title: string; url: string }[]>;
}
```

Required report section keys are listed in `REPORT_SECTIONS` in `backend/app/workflow/graph.py`.

## Frontend Architecture

The frontend is intentionally simple and currently lives mostly in `frontend/src/main.tsx`.

Important behavior:

- `request<T>()` wraps `fetch`
- `loadSessions()` populates the sidebar
- `loadActive()` fetches a session detail
- `EventSource` subscribes to `/sessions/{id}/events`
- `createSession()` posts a new session with `auto_run: true`
- `rerun()` calls the backend run endpoint
- `sendChat()` optimistically appends a user message and assistant loading placeholder
- `ReportView` renders the backend report sections

When adding new backend fields, update both the Pydantic models and the TypeScript types.

## Coding Conventions

- Keep edits small and assignment-focused.
- Prefer existing helper functions and file boundaries over introducing new frameworks.
- Backend code uses standard typed Python with Pydantic models and simple functions.
- Frontend code uses React function components and local state.
- Keep API contracts explicit and stable.
- Preserve deterministic no-key behavior so reviewers can run the app without paid credentials.
- Do not require new external services unless the change explicitly asks for them.

## Known Gotchas

- The backend README port (`8000`) and frontend default API URL (`8001`) are inconsistent.
- `analysis_node` should always define an `analysis` object, including when no Gemini key is configured.
- The UI progress steps and graph node names are not perfectly aligned around `analysis` vs `synthesis`.
- `SessionDetail` uses mutable-looking default list values in Pydantic models; prefer `Field(default_factory=list)` if touching those schemas.
- SQLite is local assignment storage, not a production concurrency solution.

## RTK (Rust Token Killer) Integration

This repository uses RTK to reduce token consumption when Copilot executes shell commands or analyzes command output.

### General Rules

* Prefer RTK for all shell commands that produce non-trivial output.
* Use RTK when reading files, searching code, running tests, inspecting git changes, or listing directories.
* Do not use RTK for simple commands that produce negligible output (e.g. `pwd`, `echo`, `whoami`).

### Preferred Commands

Instead of:

```bash
git diff
```

Use:

```bash
rtk git diff
```

Instead of:

```bash
git status
```

Use:

```bash
rtk git status
```

Instead of:

```bash
find .
```

Use:

```bash
rtk find .
```

Instead of:

```bash
rg "SessionDetail"
```

Use:

```bash
rtk rg "SessionDetail"
```

### Python Environment

This repository uses a local virtual environment located at:

```text
backend/.venv
```

Never assume the virtual environment is activated.

Use the explicit interpreter path:

```bash
./backend/.venv/bin/python
```

### Running Tests

Do not use:

```bash
pytest
```

Use:

```bash
rtk ./backend/.venv/bin/python -m pytest
```

or

```bash
rtk ./backend/.venv/bin/python -m pytest -q
```

### Running Backend

Do not assume `uvicorn` is globally available.

Use:

```bash
rtk ./backend/.venv/bin/python -m uvicorn app.main:app --reload
```

when backend execution is required.

### Reading Large Files

For large files, prefer targeted searches before reading entire files.

Examples:

```bash
rtk rg "analysis_node" backend/app/workflow/graph.py
```

```bash
rtk rg "sendChat" frontend/src/main.tsx
```

Avoid reading large files in full unless necessary.

### Code Investigation Workflow

Preferred order:

1. Read this file.
2. Use `rtk rg` to locate relevant symbols.
3. Read only the relevant files or sections.
4. Make changes.
5. Run the smallest relevant verification command through RTK.
6. Summarize findings and changes.

### Verification Commands

Backend:

```bash
rtk ./backend/.venv/bin/python -m pytest
```

Frontend:

```bash
cd frontend && rtk npm run build
```

Search:

```bash
rtk rg "<symbol>"
```

Git Review:

```bash
rtk git diff
```

```bash
rtk git status
```


## Good Copilot Workflow

Before making changes:

1. Read this file.
2. Use `rtk rg` to locate relevant code before opening files.
3. Read only the relevant key files above.
4. Check `README.md` if the change touches setup or API behavior.
5. Verify using RTK-wrapped commands.
6. Review changes with `rtk git diff`.
7. Check `architecture.md` if the change touches workflow, persistence, or cross-service contracts.

After making changes:

1. Run the smallest relevant verification command.
2. Update this file if a convention, command, route, env var, or architecture decision changes.
