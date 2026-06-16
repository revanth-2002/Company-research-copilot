## Plan: Code Quality Review and Improvement Plan

TL;DR - The current repo is a small, functional full-stack assignment with acceptable demo-level practices, but it would benefit from targeted improvements in frontend structure, backend persistence, and project hygiene.

**Steps**

1. Summarize current status and good practices found.
2. Identify quick-win hygiene gaps: missing test/lint config, `@ts-ignore` CSS import, no explicit type file or component separation.
3. Recommend frontend refactor areas: split `frontend/src/main.tsx`, extract API and SSE helpers, tighten event typing, and add tests.
4. Recommend backend refactor areas: improve config handling, reduce JSON-in-SQLite coupling, add session/chat schema separation or clearer persistence helpers, and add API/workflow tests.
5. Define verification steps: run frontend dev server, run backend API with sample session, add one test suite for each side.

**Relevant files**

- `/Users/vikrambabugaddam/Documents/zylabs_assignment/frontend/src/main.tsx` — single-file app with combined state, event handling, and UI.
- `/Users/vikrambabugaddam/Documents/zylabs_assignment/frontend/package.json` — dependency manifest; no lint/test tools currently configured.
- `/Users/vikrambabugaddam/Documents/zylabs_assignment/backend/app/main.py` — FastAPI routes and SSE streaming.
- `/Users/vikrambabugaddam/Documents/zylabs_assignment/backend/app/db.py` — SQLite persistence layer with JSON string columns.
- `/Users/vikrambabugaddam/Documents/zylabs_assignment/backend/app/workflow/graph.py` — workflow orchestration and Gemini integration.
- `/Users/vikrambabugaddam/Documents/zylabs_assignment/backend/requirements.txt` — backend dependencies.

**Verification**

1. Confirm frontend builds and loads by running `cd frontend && npm install && npm run dev`.
2. Confirm backend starts and serves endpoints by running the FastAPI app and checking `GET /health`, `GET /sessions`, and `/sessions/{id}/events`.
3. Add minimal test harnesses: one Vitest/React test for the chat UI or `request` helper, and one pytest suite for session creation + workflow state.

**Decisions**

- This is a small app, so the current code is acceptable for an assignment/demo, but not ideal for a production codebase.
- The user asked whether changes are needed: yes, for maintainability and future growth, especially around testing, folder structure, and backend persistence.

**Further Considerations**

1. Add a lint/formatter config (`eslint`, `prettier`, `black`, `ruff`) before doing larger refactors.
2. Consider separating frontend types into `frontend/src/types.ts` and backend schemas into `backend/app/schemas.py`.
3. For better production readiness, replace plain JSON storage in SQLite with normalized tables or a lightweight ORM.
