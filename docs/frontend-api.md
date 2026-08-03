# Frontend API & Event Protocol

The backend (`server.py`) is **frontend-agnostic**: it serves a WebSocket event
stream + a few REST endpoints. Any frontend (the current vanilla `index.html`,
or a future React/Svelte app) just consumes this contract. This doc is the spec
for building a new frontend.

Run the backend: `.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000`

---

## REST endpoints

| Method | Path | Body / Params | Response |
|--------|------|---------------|----------|
| GET | `/` | — | Serves the frontend HTML |
| GET | `/static/*` | — | Static assets (e.g. `/static/vendor/plotly.min.js`) |
| GET | `/api/models` | — | `{ "provider": "openai"\|"ollama", "models": ["..."], "error"? }` |
| GET | `/api/conversations` | — | `[{ "id", "title", "updated" }]` (newest first) |
| DELETE | `/api/conversations/{id}` | — | `{ "ok": true }` |
| POST | `/api/upload` | multipart: `session_id`, `file` | `{ "ok", "type": "image"\|"doc", "name", "chunks"? }` |

`session_id` for upload comes from the WebSocket `session` event (below).

---

## WebSocket `/ws`

### Client → server

```jsonc
{ "type": "user_message", "content": "...", "model": "<optional model id>",
  "deep_research": false }   // deep_research=true routes the turn through DeepSearch
{ "type": "approval_response", "id": "<approval id>", "approved": true }
{ "type": "resume", "id": "<thread_id>" }   // load a saved conversation
{ "type": "new" }                            // start a fresh conversation
{ "type": "persist", "ui": { "messages": [...], "artifacts": [...] } } // save rich UI state for this thread
```

`persist` lets the frontend store the full agent process (thinking, tool cards,
terminal, artifacts) — not just the final answer — so a resumed conversation
looks exactly as it did live. Send it when a turn finishes (`done`). The payload
is the frontend's own view model; the backend stores it verbatim under the
conversation's `ui` key and returns it on `resume` (see `history.ui`).

### Server → client

```jsonc
{ "type": "session", "id": "<sid>", "thread_id": "<tid>" }   // on connect
{ "type": "step", "thought": "...", "plan": ["...", "..."] } // non-streamed fallback: whole reasoning step at once
{ "type": "thinking", "text": "..." }                        // live reasoning delta (streamed decision)
{ "type": "thinking", "done": true }                         // reasoning finished (collapse the live thought)
{ "type": "thinking", "reset": true }                        // drop a partial thought (parse failed → retry)
{ "type": "plan", "plan": ["...", "..."] }                   // live plan/to-do update as items form
{ "type": "tool_start", "id": "<tool id>", "name": "data_analyst", "args": {...} }
{ "type": "tool_end", "id": "<tool id>", "name": "...", "result": "text", "artifacts": [...] }
{ "type": "token", "text": "..." }        // streaming final-answer chunk
{ "type": "final", "text": "..." }        // full final answer
{ "type": "notice", "text": "...", "level": "info"|"warn"|"error" }
{ "type": "approval_request", "id": "<id>", "title": "...", "detail": "markdown" }
{ "type": "history", "thread_id": "<tid>", "messages": [{ "role", "content" }], "ui"?: {...} } // after resume; `ui` = persisted rich state if present
{ "type": "thread", "id": "<tid>" }       // after "new"
{ "type": "done" }                         // turn finished (re-enable input)
```

### Turn lifecycle

```
user_message
  → thinking*  (live reasoning delta) ; plan*  (live to-do)   // streamed decision
      ‖ or, non-streamed fallback: step (thought + plan) at once
  → tool_start / tool_end   (0..N, may repeat across steps)
      ↳ approval_request → (client) approval_response   // HITL, blocks the tool
  → token*  then  final     // answer (streams live within the decision, or via token*)
  → done
  ← (client) persist        // frontend saves rich UI state for resume
```

`approval_request` can arrive mid-turn (file edits, host shell commands). The
client MUST keep receiving and reply with `approval_response` — the agent runs
in a background task so the socket stays free.

---

## Artifact descriptors (`tool_end.artifacts[]`)

```jsonc
{ "type": "image",   "data": "data:image/png;base64,..." }   // matplotlib plots
{ "type": "plotly",  "json": "<plotly figure JSON>" }         // Plotly.newPlot(el, fig.data, fig.layout)
{ "type": "table",   "html": "<table>...</table>" }           // DataFrame.head
{ "type": "links",   "items": [{ "title", "link", "snippet" }] } // web_search
{ "type": "text",    "text": "..." }

// Rich file preview (produced files). `kind` selects the viewer; the payload is
// inlined so the frontend needs no extra fetch:
{ "type": "file", "path": "...", "name": "report.html", "kind": "html",
  "text": "<source for html/markdown/csv/text kinds>",
  "table_html": "<pandas head() html for csv/excel>",
  "data": "data:application/pdf;base64,..." }   // pdf/binary, size-capped (may be absent if too large)
// kind ∈ html | markdown | csv | excel | pdf | text | binary
```

Legacy note: older builds emitted `{ "type": "file", "path": "..." }` with no
`kind`. Frontends should tolerate a missing `kind`/payload and fall back to
showing the path.

---

## Notes for the new (React/Svelte) frontend

- **Markdown + code**: render `final` (and streamed `token`) as Markdown with
  syntax-highlighted code blocks. Sanitize model output (e.g. `marked` +
  `highlight.js` + `DOMPurify`). Vendor them locally for offline use.
- **Artifacts side panel** (3-column layout: conversations | chat | artifacts):
  route `tool_end.artifacts` into a right panel instead of inline.
  - `plotly` → interactive chart, `table` → rendered table, `image` → `<img>`,
    `links` → sources list (web search: which URLs were visited).
  - **HTML/Markdown/file preview** (Claude-artifacts style): show code + a
    rendered view (HTML in a sandboxed `<iframe srcdoc>`). Backed by the rich
    `file` descriptor above (`_serialize_artifacts` in `backend/core/agent.py`
    inlines the payload — no extra fetch needed).
- **Serving**: build the SPA to static files and let FastAPI serve them (mount
  or `/`), or run Vite dev-server proxying `/ws` + `/api` to :8000.
- The event/REST contract above is the stable seam — extend it additively.
