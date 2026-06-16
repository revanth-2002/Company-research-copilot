# Follow-up Chat API Flow

This document describes the streaming follow-up chat flow for the ZyLabs Research Copilot, including API behavior, SSE events, DB interactions, frontend handling, error cases, and suggested improvements.

## Goals
- Provide a responsive UX where the assistant shows a loading/flicker placeholder when a follow-up question is asked.
- Deliver partial assistant text progressively (streaming) rather than returning the full answer at once.
- Persist chat messages in SQLite and broadcast incremental updates over the existing SSE channel.

## API Endpoints

- `POST /sessions/{session_id}/chat`
  - Request body: `{ "message": "<user question>" }`
  - Response: `202 Accepted` (or minimal `200` with acknowledgement). The real answer is produced asynchronously.
  - Server actions (synchronous):
    1. Validate `session_id` exists and permissions.
    2. Call `append_chat(session_id, "user", message)` to persist the user message.
    3. Create an assistant placeholder chat entry: `{ role: "assistant", content: "", timestamp: "<ts>", loading: true }` using `append_chat`.
    4. Broadcast an initial event so clients render the assistant placeholder.
    5. Start an asynchronous background task that performs LLM streaming and publishes deltas.

## SSE Events and Shapes

- Reuse `GET /sessions/{session_id}/events` (text/event-stream).
- Event types:
  - `session`: full session snapshot (existing contract).
  - `chat_delta`: incremental chat update. Example payload:
    ```json
    {
      "type": "chat_delta",
      "session_id": "...",
      "ts": "pending-165...",
      "chunk": "partial text",
      "done": false
    }
    ```
  - `chat_done`: finalization event (may be merged with `chat_delta` using `done: true`).

Notes:
- Use `ts` (timestamp or placeholder id) to identify which assistant placeholder to update on the client.
- For efficiency, stream `chat_delta` events rather than broadcasting entire session objects for every chunk.

## Backend DB changes

- Chat rows must be updatable. Current schema stores `chat` as a JSON array in the sessions table. Add helper functions:
  - `append_chat(session_id, role, content, timestamp?)` — already exists.
  - `update_chat_message(session_id, timestamp, content, loading=False)` — new helper that updates the in-DB chat array entry matching `timestamp` and then calls `broadcast_session_event` or emits `chat_delta`.

- Implementation guidance:
  - `update_chat_message` should load the session, mutate the chat array (replace the matching message content/loading), write back with `update_session(..., chat=chat_array)`, and then emit either a `chat_delta` event or the full `session` snapshot.
  - Prefer emitting `chat_delta` events for each chunk to avoid heavy payloads.

## Server streaming implementation (sketch)

1. Background task starts LLM streaming call for the prompt (prompt includes the report + follow-up question).
2. For each chunk received from the LLM stream:
   - Call `update_chat_message(session_id, placeholder_ts, cumulative_text, loading=True)` OR emit `chat_delta` with the chunk.
3. On error:
   - Call `update_chat_message(session_id, placeholder_ts, "Error: ...", loading=False)` and emit a final `chat_delta(done=true)`.
4. On completion:
   - Persist final content and `loading=false` and emit `chat_delta(done=true)`.

Implementation notes:
- Use the provider's streaming API where possible (e.g., GenAI's `stream_generate_content` or bidi endpoints) so chunks arrive naturally.
- Ensure the background task is resilient to transient network errors; implement retries with exponential backoff for the LLM call.

## Frontend consumer behavior

1. On chat submit:
   - Append the user message locally.
   - Append assistant placeholder message with `timestamp = placeholder_ts` and `loading = true`.
   - Disable or partially disable the input to prevent duplicate sends (optional).
   - Send `POST /sessions/{session_id}/chat` and rely on SSE updates for streaming chunks.
2. SSE handler:
   - On `chat_delta`: find local message with `timestamp === ts` and update its `content` by applying the chunk (either append or replace with cumulative text). If `done: true`, set `loading=false`.
   - On `session` events: reconcile the full chat array using `timestamp` values as the canonical source of truth (to avoid duplicates).
3. UX:
   - While placeholder `loading=true`, show flicker animation and a subtle placeholder text such as `Loading context`.
   - Reveal text progressively as chunks arrive (smooth streaming effect).
   - On finalization, remove flicker and show final content.

## Error handling and edge cases

- LLM stream error: emit a final `chat_delta` with `done: true` and `chunk: "Error fetching response"` so the UI can show a failure state and re-enable input.
- Client disconnects (SSE closed): server should continue and persist final answer; when client reconnects it will receive the final `session` snapshot.
- Chunk ordering: rely on a single stream per placeholder; if multiple parallel placeholders exist (rare), ensure `ts` ties chunks to the correct placeholder.
- Deduplication: frontend should ignore duplicate `chat_delta` chunks if they match already-applied content (idempotent updates).

## Improvements & optimizations

- Use a lightweight delta shape rather than full session snapshots to reduce SSE bandwidth.
- Add a small `sequence` or `offset` integer in `chat_delta` to guarantee ordering at the client.
- Persist chat messages as separate rows (normalize) rather than a JSON column for better update efficiency and concurrency.
- Add authentication and session ownership checks to the `POST /sessions/{id}/chat` endpoint.
- Rate limit follow-up calls per session to avoid abuse and runaway token costs.
- Offer server-side streaming compression or batching if many small chunks are emitted.
- Provide a `retry`/`resume` token for interrupted streams so clients can resume instead of restarting.
- Instrument metrics (latency, chunk count, errors) for monitoring and alerting.

## Minimal migration steps (developer checklist)

- Add `update_chat_message(session_id, timestamp, content, loading=False)` in `backend/app/db.py`.
- Enhance `backend/app/events.py` to support emitting `chat_delta` events.
- Change `POST /sessions/{session_id}/chat` (in `backend/app/main.py`) to:
  - append user chat, create placeholder assistant chat, broadcast initial state, and start a background streaming task.
- Update frontend SSE handler to apply `chat_delta` updates and keep placeholder timestamps as keys.
- Add unit/integration tests around streaming chat, chunk ordering, and reconnect behavior.

---

If you'd like, I can now:

- Implement `update_chat_message` and `chat_delta` broadcasting in `backend/app/db.py` and `backend/app/events.py` (small patch).
- Implement server-side streaming call skeleton using the GenAI stream API in `backend/app/main.py` (background task), and update frontend SSE `onmessage` handling to apply `chat_delta` events.

Which of those would you like me to implement next?
