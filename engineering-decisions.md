# Engineering Decisions

## 1. FastAPI Backend With Explicit Session APIs

Decision: Use FastAPI as the backend boundary for sessions, workflow execution, and chat.

Alternatives considered:

- Next.js API routes
- Flask
- A single Python script with a Streamlit UI

Tradeoffs:

- FastAPI adds a small amount of project structure, but it gives typed request validation, OpenAPI docs, async-friendly endpoints, and a clean production path.
- Keeping the backend separate from the frontend makes the LangGraph workflow easier to test and evolve independently.

## 2. LangGraph Multi-Node Workflow

Decision: Implement the AI process as a LangGraph state machine with planner, research, analysis, quality check, conditional retry, and report generation nodes.

Alternatives considered:

- A single LLM prompt that returns the full report
- A linear chain without routing
- A custom workflow runner

Tradeoffs:

- LangGraph is more explicit and slightly more verbose.
- The benefit is inspectability, recoverability, intermediate outputs, and a clear way to add more agents or tools later.
- The conditional quality route directly supports product-grade behavior instead of hiding failures behind a single response.

## 3. MongoDB for Persistence

Decision: Use MongoDB with a document-oriented data layer.

Alternatives considered:

- SQLite
- Postgres with SQLAlchemy
- In-memory state

Tradeoffs:

- Session progress events and report sections are deeply nested JSON. MongoDB stores them as native documents without schema migrations or JSON serialization overhead.
- Flexible enough for the assignment without standing up a relational schema upfront.
- In production, replica sets and Atlas provide horizontal scaling and managed backups.

## 4. Real-time Updates: SSE Considered, WebSocket Chosen

Decision: Use WebSocket (`WS /sessions/{session_id}/ws`) for pushing live session updates from FastAPI to the React UI.

Why not plain HTTP request-response:

The research workflow runs as a background task and returns immediately after session creation — the report is not ready yet. A single HTTP request cannot wait minutes for the workflow to finish without hitting browser and server timeouts, and it gives the user no visibility into progress. Real-time streaming was required from the start.

Why SSE was evaluated first:

Server-Sent Events are simpler to implement for one-way server-to-client streams. The browser's native `EventSource` API handles reconnects automatically. SSE was the initial implementation.

Why WebSocket was chosen instead:

The browser's native `EventSource` API cannot send custom headers, which made attaching the Clerk JWT for authentication impossible without passing the token as a query parameter — an acceptable workaround but a sign of protocol mismatch. WebSocket's initial HTTP upgrade handshake supports query parameters natively for the same token-passing approach, while also opening the door to bidirectional communication (e.g. streaming LLM tokens back to the client, or sending client-side commands during a running workflow). The added complexity over SSE is minimal in FastAPI, which has first-class WebSocket support.

Alternatives considered:

- Polling `GET /sessions/{id}` — simplest, auth works, but creates unnecessary load and feels laggy for a workflow that takes 30–120 seconds.
- Waiting for workflow completion — eliminates streaming entirely but freezes the UI with no progress feedback.

## 5. Clerk for Authentication

Decision: Use Clerk for user identity, JWT issuance, and session management.

Alternatives considered:

- Rolling custom JWT auth with FastAPI
- Firebase Auth
- No auth for the assignment

Tradeoffs:

- Clerk provides login, signup, social login, and JWT issuance with zero backend infrastructure and a first-class React SDK.
- The backend verifies JWTs against Clerk's JWKS endpoint — no user table or password storage required.
- Clerk's hosted UI components handle the full auth flow, keeping the frontend focused on the product.

## 6. Gemini Provider Boundary

Decision: Keep AI synthesis isolated behind a Gemini configuration boundary using `GEMINI_API_KEY`.

Alternatives considered:

- Require a paid API key across the entire app
- Use only deterministic templates for report generation
- Add multiple provider integrations up front

Tradeoffs:

- Gemini support makes the demo more realistic while keeping provider-specific code mostly inside the workflow layer.
- A deterministic fallback helper exists, but the no-key synthesis path should be wired and tested before treating offline report generation as supported.
- Research quality remains limited until live search, richer prompts, and citation-level evidence are added.

## Top Technical Debt

- The WebSocket subscription layer is in-memory, so it is not ready for multi-process production deployment — a pub/sub broker (Redis, etc.) is needed.
- The no-key analysis fallback is not fully wired into the active synthesis path.
- There is no committed automated test suite yet.
- Tenant isolation and per-user quotas are not yet implemented on top of the existing Clerk auth.

## Biggest Technical Risk

The biggest risk is research quality. A sales copilot is only useful if its evidence is timely, sourced, and specific. Production should add live search, enrichment APIs, source ranking, quote extraction, and citation-level traceability.

## What I Would Improve With Two Additional Weeks

- Add durable LangGraph checkpointing backed by MongoDB.
- Add Tavily/SerpAPI/Exa or a similar search provider.
- Add source cards with confidence levels and extracted evidence.
- Harden WebSocket reconnect and message delivery for multi-worker deployments.
- Add automated backend tests and frontend component tests.
- Add tenant isolation, user ownership, and rate limits on top of existing Clerk auth.
- Add export to PDF or Google Docs for the final briefing.
