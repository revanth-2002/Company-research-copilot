# Research Copilot Session Flow

This document describes the execution flow for one session run in the AI Research Copilot application.

## 1. Frontend submits the research request
- `App.createSession()` is called when the user submits the research form.
- It sends `POST /sessions` with:
  - `company_name`
  - `website`
  - `objective`
  - `auto_run: true`

## 2. Backend creates the session
- `backend/app/main.py` → `create_research_session(payload)`
  - generates a new `session_id`
  - calls `backend/app/db.py` → `create_session(session_id, company_name, website, objective)`
- `create_session(...)` inserts a new row into SQLite with:
  - `status = 'queued'`
  - `progress = '[]'`
  - `errors = '[]'`
  - `chat = '[]'`
  - timestamps
- Returns the created session record.

## 3. Backend schedules the workflow
- `create_research_session()` uses FastAPI `BackgroundTasks` to call:
  - `run_research_workflow(session_id)`
- The request returns immediately, and the workflow executes in the background.

## 4. Workflow initializes
- `backend/app/workflow/graph.py` → `run_research_workflow(session_id)`
  - loads the session via `get_session(session_id)`
  - updates the session status to `running`
  - creates the initial state object
  - invokes the graph with `research_graph.invoke(initial_state)`

## 5. Graph execution order
The graph nodes are executed in this order:
1. `planner`
2. `research`
3. `synthesis`
4. `quality_check`
5. conditional transition
   - either back to `research`
   - or to `report_generation`
6. `report_generation`
7. end

## 6. Node responsibilities

### planner
- writes progress:
  - `planner running`
  - `planner complete`
- returns a partial state with:
  - `plan`
  - `retries`

### research
- writes progress:
  - `research running`
- fetches the target website with `httpx`
- cleans HTML text using `_clean_text()`
- writes progress:
  - `research complete`
- returns a partial state with:
  - `raw_research`
  - `errors`

### synthesis
- writes progress:
  - `analysis running`
- reads `raw_research.website_text`
- optionally calls Gemini with `_call_gemini(...)`
- parses model output into JSON with `_parse_json_response()`
- writes progress:
  - `analysis complete`
- returns a partial state with:
  - `analysis`

### quality_check
- writes progress:
  - `quality_check running`
- computes completeness score across `REPORT_SECTIONS`
- writes progress:
  - `quality_check complete`
- returns a partial state with:
  - `quality_score`
  - `retries`

### route_after_quality
- reads `quality_score` and `retries`
- returns the next node name:
  - `report_generation` when score >= 0.9
  - `research` when score is low and retries < 2
  - `report_generation` when retries are exhausted

### report_generation
- writes progress:
  - `report_generation running`
- reads `analysis` and `quality_score`
- builds the final `report` object with:
  - `title`
  - `objective`
  - `sections`
  - `quality_score`
- writes progress:
  - `report_generation complete`
- returns a partial state with:
  - `report`

## 7. Graph state and final output
- `StateGraph` merges each node's returned partial state into the shared state.
- The final output from `research_graph.invoke(...)` includes all accumulated keys from every node:
  - `company_name`, `website`, `objective`
  - `plan`, `raw_research`, `analysis`, `quality_score`, `retries`, `errors`, `report`
- `run_research_workflow()` extracts `final_state['report']` and saves it into the session.

## 8. Completion
- After the graph finishes, `run_research_workflow()`:
  - extracts the final `report`
  - updates session status to `completed`
  - saves the report and any errors
- If an exception occurs, the session is updated to `failed` with the error.

## 8. Session persistence and streaming
- `backend/app/db.py` → `update_session()`
  - writes updated session state to SQLite
  - reloads the session
  - broadcasts the updated session via SSE
- This means every state update is pushed to connected frontend clients.

## 9. Frontend SSE handling
- `frontend/src/main.tsx` opens `EventSource("${API_URL}/sessions/${activeId}/events")` when a session is active.
- The frontend receives:
  - initial session state
  - subsequent session update events
- Each event updates the active session state in React.

## 10. Call chain summary
1. `App.createSession()`
2. `POST /sessions`
3. `create_research_session()`
4. `create_session()`
5. `background_tasks.add_task(run_research_workflow, session_id)`
6. `run_research_workflow()`
7. `get_session()`
8. `update_session(status="running")`
9. `research_graph.invoke()`
10. `planner_node()`
11. `research_node()`
12. `analysis_node()`
13. `quality_node()`
14. `route_after_quality()`
15. `report_node()`
16. `update_session(status="completed", report=...)`
17. SSE sends session updates to frontend
