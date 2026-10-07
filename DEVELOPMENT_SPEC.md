# Development Specification — Developer Docs Chatbot

## Project Goals

A production-quality RAG chatbot for developer documentation that:
- Indexes any documentation URL via web scraping
- Answers natural language questions with source citations
- Streams responses in real time (SSE) for a responsive UX
- Persists chat history per session
- Demonstrates senior-level, readable, well-structured code

**Out of scope for this phase:**
- Authentication / multi-user support
- Production deployment (no load balancer, no SSL)
- PDF / file upload (URL-only ingestion)
- Paid embedding APIs (local Ollama is sufficient)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│             Vite + React + TypeScript + TailwindCSS         │
│                                                             │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │   ChatView   │  │  SessionList   │  │  SourcesView   │  │
│  └──────────────┘  └────────────────┘  └────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │       useChat  useSSE  useSources  useSession         │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────┐
│                      FastAPI Backend                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  API Layer (app/api/)                                 │   │
│  │  /api/sessions  /api/sources  /api/health            │   │
│  └───────────┬──────────────┬───────────────┬───────────┘   │
│              │              │               │               │
│  ┌───────────▼──┐  ┌────────▼──────┐  ┌────▼────────────┐  │
│  │ ChatService  │  │IngestionSvc   │  │RetrievalService  │  │
│  └───────────┬──┘  └────────┬──────┘  └────┬────────────┘  │
│              │              │               │               │
│  ┌───────────▼──┐  ┌────────▼──────┐  ┌────▼────────────┐  │
│  │  Anthropic   │  │ OllamaClient  │  │ pgvector query  │  │
│  │  SDK (SSE)   │  │ (embeddings)  │  │ (cosine sim)    │  │
│  └──────────────┘  └───────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────▼───────────────┐
            │    PostgreSQL 16 + pgvector   │
            │  sources | chunks | sessions  │
            │  messages                     │
            └───────────────────────────────┘
```

### Request Data Flow

```
User question
    → embed question (Ollama)
    → cosine search in pgvector (top-5 chunks, filtered by session.source_ids)
    → assemble prompt (system + context + history + question)
    → stream response from Claude Haiku 4.5 (Anthropic SDK)
    → SSE token events → frontend
    → persist message + sources to DB
    → SSE done event
```

---

## Database Schema

```sql
-- Documentation sources (indexed websites)
CREATE TABLE sources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    base_url    TEXT NOT NULL UNIQUE,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    -- 'pending' | 'indexing' | 'ready' | 'error'
    chunk_count INT NOT NULL DEFAULT 0,
    error_msg   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Text chunks with embedding vectors
CREATE TABLE chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    title       TEXT,
    content     TEXT NOT NULL,
    token_count INT,
    embedding   vector(768),  -- nomic-embed-text dimensions
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Chat sessions
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT,           -- auto-generated from first user message
    source_ids  UUID[] NOT NULL DEFAULT '{}',
    -- empty = search all sources
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chat messages
CREATE TABLE messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    sources     JSONB,  -- [{url, title, score}] for assistant messages
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON messages (session_id, created_at);
```

---

## API Contract

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/sessions | Create new session |
| GET | /api/sessions | List all sessions |
| GET | /api/sessions/{id} | Get session with messages |
| DELETE | /api/sessions/{id} | Delete session |
| POST | /api/sessions/{id}/messages | Send message (returns SSE stream) |

### Sources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/sources | List all sources with status |
| POST | /api/sources | Add URL and trigger background indexing |
| GET | /api/sources/{id} | Get source details |
| DELETE | /api/sources/{id} | Remove source and all its chunks |
| POST | /api/sources/{id}/reindex | Re-index a source |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | DB + Ollama + Anthropic status |

### SSE Streaming Format

`POST /api/sessions/{id}/messages` returns an SSE stream:

```
event: token
data: {"content": "Hello"}

event: token
data: {"content": " world"}

event: sources
data: {"sources": [{"url": "...", "title": "...", "score": 0.92}]}

event: done
data: {"message_id": "uuid", "session_id": "uuid"}

event: error
data: {"message": "error description"}
```

---

## Project Structure (detailed)

```
backend/app/
├── main.py                  # FastAPI app factory, middleware, startup events
├── config.py                # Pydantic-settings: all env vars validated at startup
├── exceptions.py            # Domain-specific exceptions
├── api/
│   ├── __init__.py
│   ├── sessions.py          # Session + message endpoints
│   ├── sources.py           # Source CRUD + indexing trigger
│   └── health.py            # Health check
├── services/
│   ├── __init__.py
│   ├── chat.py              # ChatService: history assembly, prompt, streaming
│   ├── retrieval.py         # RetrievalService: embed query + pgvector search
│   └── ingestion.py         # IngestionService: scraping, chunking, indexing
├── db/
│   ├── __init__.py
│   ├── connection.py        # asyncpg pool setup
│   ├── migrate.py           # Migration runner
│   └── migrations/
│       ├── 001_initial.sql
│       └── 002_indexes.sql
├── models/
│   ├── __init__.py
│   ├── session.py           # Session + Message Pydantic models
│   └── source.py            # Source Pydantic models
└── clients/
    ├── __init__.py
    ├── ollama.py            # Ollama HTTP client (httpx)
    └── anthropic.py         # Anthropic SDK wrapper (streaming)

frontend/src/
├── main.tsx
├── App.tsx
├── components/
│   ├── ChatView/
│   │   ├── index.tsx
│   │   ├── MessageList.tsx
│   │   ├── MessageItem.tsx
│   │   └── ChatInput.tsx
│   ├── SessionList/
│   │   ├── index.tsx
│   │   └── SessionItem.tsx
│   ├── SourcesView/
│   │   ├── index.tsx
│   │   ├── SourceItem.tsx
│   │   └── AddSourceForm.tsx
│   └── ui/                  # Generic UI primitives (Button, Badge, Spinner)
├── hooks/
│   ├── useChat.ts
│   ├── useSources.ts
│   ├── useSession.ts
│   └── useSSE.ts
├── api/
│   ├── client.ts            # Base fetch wrapper
│   ├── sessions.ts
│   └── sources.ts
└── types/
    ├── session.ts
    └── source.ts
```

---

## Development Phases

### Phase 1 — Infrastructure and Project Skeleton

**Goal:** everything runs, services are connected, foundation is solid.

Tasks:
- [ ] `docker-compose.yml`: PostgreSQL 16 + pgvector + Ollama service
- [ ] `.env.example` + pydantic-settings config
- [ ] FastAPI app factory (`main.py`), CORS, structured logging
- [ ] asyncpg connection pool
- [ ] SQL migrations (sources, chunks, sessions, messages + indexes)
- [ ] `GET /api/health` — DB + Ollama status
- [ ] Vite + React + TypeScript + TailwindCSS scaffold
- [ ] `pyproject.toml`: ruff, mypy, pytest configuration

Acceptance criteria:
- `docker compose up` starts all services healthy
- `GET /api/health` returns 200 with DB + Ollama status
- Frontend dev server starts and connects to the API

---

### Phase 2 — Document Ingestion

**Goal:** a URL becomes searchable chunks in the database.

Tasks:
- [ ] `IngestionService`: web scraper (httpx + BeautifulSoup4)
- [ ] Recursive text splitter (500 tokens/chunk, 50-token overlap)
- [ ] Embedding generation via Ollama (`nomic-embed-text`)
- [ ] Async background task (FastAPI `BackgroundTasks`)
- [ ] Source status transitions: pending → indexing → ready / error
- [ ] `POST /api/sources`, `GET /api/sources`, `DELETE /api/sources/{id}`
- [ ] Pytest unit tests: chunker, scraper mock

Acceptance criteria:
- A real docs URL (e.g., https://tailwindcss.com/docs/installation) is successfully indexed
- Chunks with embedding vectors appear in the DB
- Source status transitions correctly

---

### Phase 3 — RAG Core (non-streaming)

**Goal:** question → accurate answer with source citations (no streaming yet).

Tasks:
- [ ] `RetrievalService`: query embedding + pgvector cosine search (top-5)
- [ ] Context assembly with source metadata
- [ ] System prompt template (context + question)
- [ ] Claude Haiku 4.5 integration (Anthropic SDK, non-streaming)
- [ ] `POST /api/sessions`, `POST /api/sessions/{id}/messages` (blocking)
- [ ] Persist response + sources to DB
- [ ] Pytest integration test: full RAG pipeline

Acceptance criteria:
- Question returns a relevant answer with source citations
- Context window management handles long histories (truncation)
- Tests pass

---

### Phase 4 — Chat History and Session Management

**Goal:** multi-turn conversation with history loaded from the database.

Tasks:
- [ ] Session CRUD: create, list, get (with messages), delete
- [ ] Chat history included in prompt (last N messages)
- [ ] Auto-generate session title from first user message
- [ ] Source selection per session (`session.source_ids`)
- [ ] `GET /api/sessions/{id}` returns full message list

Acceptance criteria:
- Multi-turn conversation correctly references earlier messages
- History is fetched from DB, not held in memory
- Session deletion cascades to messages

---

### Phase 5 — SSE Streaming

**Goal:** real-time token display in the frontend.

Tasks:
- [ ] FastAPI `StreamingResponse` SSE implementation
- [ ] Token-by-token reading from Anthropic SDK `.stream()`
- [ ] Sources event sent after stream completes
- [ ] Frontend `EventSource` hook (`useSSE`)
- [ ] Graceful error handling (error event, connection drop)
- [ ] Message persisted to DB on stream completion

Acceptance criteria:
- Tokens appear in real time in the UI
- No full-response buffering on the backend
- Network errors surface as a visible UI state, not a frozen screen

---

### Phase 6 — Frontend

**Goal:** a complete, usable UI.

Tasks:
- [ ] `ChatView`: message list + streaming display + input
- [ ] `SessionList`: session list, new session, delete
- [ ] `SourcesView`: source list with status, add URL, delete
- [ ] Source selection on session creation
- [ ] Loading states, skeleton loaders
- [ ] Error states with user-friendly messages
- [ ] Source citation display in assistant messages
- [ ] Responsive layout (desktop-first, functional on mobile)

---

### Phase 7 — Code Quality and Testing

**Goal:** production-ready quality, full review.

Tasks:
- [ ] Pytest coverage: 80%+ backend (services + api)
- [ ] Vitest: `useChat`, `useSSE` hooks, `ChatInput`, `AddSourceForm`
- [ ] `ruff check` + `ruff format` — clean
- [ ] `mypy --strict` — zero errors
- [ ] Pre-commit hooks: ruff + mypy + pytest
- [ ] All TODOs and FIXMEs resolved
- [ ] README and DEVELOPMENT_SPEC final review

---

## Code Quality Standards

### Python (backend)

- Type hints on all public functions and methods
- Max 50 lines per function — split at natural boundaries
- Max 300 lines per file — use sub-modules
- Every endpoint has a `response_model`
- All env vars validated at startup via pydantic-settings
- Structured logging (structlog, JSON format) — no `print()` statements
- Domain-specific exceptions in `app/exceptions.py`, never bare `Exception`
- No ORM — raw asyncpg queries, well-named, self-documenting
- Async everywhere I/O is involved

### TypeScript (frontend)

- `strict: true` in tsconfig, no `any`
- Max 150 lines per component — extract business logic into hooks
- Max 100 lines per hook — split if needed
- All API responses are typed, no implicit any
- TailwindCSS only — no inline styles

---

## Testing Strategy

### Backend (Pytest)

```
tests/
├── unit/
│   ├── test_chunker.py         # Text splitter logic
│   ├── test_retrieval.py       # Retrieval service (mock DB)
│   └── test_chat_service.py    # Prompt assembly, history truncation
└── integration/
    ├── test_api_sources.py     # Source CRUD endpoints
    ├── test_api_sessions.py    # Session + message endpoints
    └── conftest.py             # Test DB setup (real PostgreSQL)
```

- Integration tests use a real test database, not mocks
- Ollama and Anthropic are mocked in all tests
- Run after each phase: `pytest --cov=app --cov-report=term-missing`

### Frontend (Vitest)

```
src/__tests__/
├── hooks/
│   ├── useChat.test.ts
│   └── useSSE.test.ts
└── components/
    ├── ChatInput.test.tsx
    └── AddSourceForm.test.tsx
```

---

## Decisions (locked 2026-10-07)

1. **Pre-seeded documentation**: Tailwind CSS + React + TypeScript docs. These will be indexed as demo data.

2. **Session source selection**: Users can select which source(s) to search when starting a session. `sessions.source_ids` holds the selection; an empty array means search all sources.

---

## Dependencies

### Backend (pyproject.toml)

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "asyncpg>=0.30",
    "anthropic>=0.40",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "pydantic-settings>=2.5",
    "structlog>=24.4",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.7",
    "mypy>=1.12",
    "pre-commit>=4.0",
]
```

### Frontend (package.json key deps)

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4",
    "typescript": "^5",
    "tailwindcss": "^3",
    "vitest": "^2",
    "@testing-library/react": "^16"
  }
}
```

---

## Spec Change Management

If the specification changes:
1. Update this file (note what changed and why)
2. Update acceptance criteria for affected phases
3. If already-written code is affected, open a rework task — do not silently drift from the spec
