# Development Specification -- Developer Docs Chatbot

## Projekt célok

Egy production-ready minőségű, de személyes/portfolio célú RAG chatbot, ami:
- Bármely fejlesztői dokumentációs URL-t be tud indexelni
- Természetes nyelvű kérdésekre pontosan válaszol, forráshivatkozásokkal
- Streaming válaszokat ad (SSE) valós idejű UX-ért
- Megőrzi a chat historyt session-önként
- Senior szintű, olvasható, jól tagolt kódbázist mutat

**Nem cél (jelen fázisban):**
- Authentikáció / multi-user support
- Production deployment (nincs load balancer, nincs SSL)
- PDF / fájl feltöltés (csak URL-alapú indexelés)
- Fizetős embedding API (Ollama lokális elegendő)

---

## Architektúra

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                            │
│             Vite + React + TypeScript + TailwindCSS         │
│                                                             │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
│  │   ChatView   │  │  SessionList   │  │  SourcesView   │  │
│  └──────────────┘  └────────────────┘  └────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         useChat  useSSE  useSources  useSession       │   │
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
│  │ ChatService  │  │IngestionSvc   │  │ RetrievalService │  │
│  └───────────┬──┘  └────────┬──────┘  └────┬────────────┘  │
│              │              │               │               │
│  ┌───────────▼──┐  ┌────────▼──────┐  ┌────▼────────────┐  │
│  │  Anthropic   │  │  OllamaClient │  │  pgvector query │  │
│  │  SDK (SSE)   │  │  (embeddings) │  │  (cosine sim)   │  │
│  └──────────────┘  └───────────────┘  └─────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
            ┌──────────────▼───────────────┐
            │    PostgreSQL 16 + pgvector   │
            │  sources | chunks | sessions  │
            │  messages                     │
            └───────────────────────────────┘
```

### Adatfolyam -- kérdés megválaszolása

```
User question
    → embed question (Ollama)
    → cosine search in pgvector (top-5 chunks)
    → assemble prompt (system + context + history + question)
    → stream to Claude Haiku 4.5 (Anthropic SDK)
    → SSE token events → frontend
    → persist message + sources to DB
    → SSE done event
```

---

## Adatbázis séma

```sql
-- Dokumentációs források (indexelt weboldalak)
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

-- Szöveg chunkok embedding vektorokkal
CREATE TABLE chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    url         TEXT NOT NULL,
    title       TEXT,
    content     TEXT NOT NULL,
    token_count INT,
    embedding   vector(768),  -- nomic-embed-text dimenzió
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Chat sessionök
CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT,           -- első kérdésből auto-generált
    source_ids  UUID[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Chat üzenetek
CREATE TABLE messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id  UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    sources     JSONB,  -- [{url, title, score}] assistant üzenetekhez
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON messages (session_id, created_at);
```

---

## API kontrakt

### Sessions

| Method | Endpoint | Leírás |
|--------|----------|--------|
| POST | /api/sessions | Új session létrehozása |
| GET | /api/sessions | Sessionök listázása |
| GET | /api/sessions/{id} | Session + üzenetek lekérése |
| DELETE | /api/sessions/{id} | Session törlése |
| POST | /api/sessions/{id}/messages | Üzenet küldése (SSE stream) |

### Sources

| Method | Endpoint | Leírás |
|--------|----------|--------|
| GET | /api/sources | Összes forrás státusszal |
| POST | /api/sources | Új URL hozzáadása + indexelés indítása |
| GET | /api/sources/{id} | Forrás részletei |
| DELETE | /api/sources/{id} | Forrás + chunkjai törlése |
| POST | /api/sources/{id}/reindex | Újraindexelés |

### System

| Method | Endpoint | Leírás |
|--------|----------|--------|
| GET | /api/health | DB + Ollama + Anthropic státusz |

### SSE streaming formátum

A `POST /api/sessions/{id}/messages` SSE stream-et ad vissza:

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
data: {"message": "hiba leírása"}
```

---

## Projekt struktúra (részletes)

```
backend/app/
├── main.py                  # FastAPI app factory, middleware, startup events
├── config.py                # Pydantic-settings: env vars validálva startup-kor
├── api/
│   ├── __init__.py
│   ├── sessions.py          # Session + üzenet endpointok
│   ├── sources.py           # Source CRUD + indexelés trigger
│   └── health.py            # Health check
├── services/
│   ├── __init__.py
│   ├── chat.py              # ChatService: history összerakás, prompt, streaming
│   ├── retrieval.py         # RetrievalService: embedding + pgvector keresés
│   └── ingestion.py         # IngestionService: scraping, chunking, indexelés
├── db/
│   ├── __init__.py
│   ├── connection.py        # asyncpg pool setup
│   ├── migrate.py           # Migrációk futtatása
│   └── migrations/
│       ├── 001_initial.sql
│       └── 002_indexes.sql
├── models/
│   ├── __init__.py
│   ├── session.py           # Session + Message Pydantic modellek
│   └── source.py            # Source Pydantic modellek
└── clients/
    ├── __init__.py
    ├── ollama.py            # Ollama HTTP kliens (httpx)
    └── anthropic.py         # Anthropic SDK wrapper (streaming)

frontend/src/
├── main.tsx
├── App.tsx
├── components/
│   ├── ChatView/
│   │   ├── index.tsx        # Fő chat nézet
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
│   └── ui/                  # Generikus UI elemek (Button, Badge, Spinner)
├── hooks/
│   ├── useChat.ts           # Üzenet küldés + SSE kezelés
│   ├── useSources.ts        # Source CRUD
│   └── useSession.ts        # Session kezelés
├── api/
│   ├── client.ts            # Base fetch wrapper
│   ├── sessions.ts
│   └── sources.ts
└── types/
    ├── session.ts
    └── source.ts
```

---

## Fejlesztési fázisok

### Fázis 1 -- Infrastruktúra és projekt skeleton

**Cél:** minden fut, össze van kötve, az alapok rendben vannak.

Feladatok:
- [ ] `docker-compose.yml`: PostgreSQL 16 + pgvector + Ollama service
- [ ] `.env.example` + pydantic-settings config
- [ ] FastAPI app factory (`main.py`), CORS, logging
- [ ] asyncpg connection pool
- [ ] SQL migrációk (sources, chunks, sessions, messages + indexek)
- [ ] `GET /api/health` -- DB + Ollama státusz
- [ ] Vite + React + TypeScript + TailwindCSS scaffold
- [ ] `pyproject.toml`: ruff, mypy, pytest konfiguráció

Elfogadási kritériumok:
- `docker compose up` sikeresen indul, minden service healthy
- `GET /api/health` 200-at ad vissza DB + Ollama státusszal
- Frontend dev szerver elindul, API-ra csatlakozik

---

### Fázis 2 -- Dokumentáció indexelés

**Cél:** URL-ből chunkok keletkeznek az adatbázisban.

Feladatok:
- [ ] `IngestionService`: web scraper (httpx + BeautifulSoup4)
- [ ] Recursive text splitter (500 token/chunk, 50 token overlap)
- [ ] Ollama embedding generálás (`nomic-embed-text`)
- [ ] Asyncio background task (FastAPI `BackgroundTasks`)
- [ ] Source státusz frissítés: pending → indexing → ready / error
- [ ] `POST /api/sources` + `GET /api/sources` + `DELETE /api/sources/{id}`
- [ ] Pytest unit tesztek: chunker, scraper mock

Elfogadási kritériumok:
- Egy valós docs URL (pl. https://tailwindcss.com/docs/installation) sikeresen indexelve
- Chunkök megjelennek a DB-ben embedding vektorokkal
- Source státusz helyesen frissül

---

### Fázis 3 -- RAG core (nem-streaming)

**Cél:** kérdés → pontos válasz forráshivatkozásokkal (streaming nélkül).

Feladatok:
- [ ] `RetrievalService`: query embedding + pgvector cosine search (top-5)
- [ ] Kontextus összerakás: chunk content + metadata
- [ ] System prompt template (kontextus + kérdés)
- [ ] Claude Haiku 4.5 integráció (Anthropic SDK, non-streaming)
- [ ] `POST /api/sessions` + `POST /api/sessions/{id}/messages` (blokkoló)
- [ ] Válasz + sources mentése DB-be
- [ ] Pytest integrációs teszt: teljes RAG pipeline

Elfogadási kritériumok:
- Kérdés → releváns válasz, forráshivatkozásokkal
- Context window kezelés (hosszú history truncation)
- Tesztek zöldek

---

### Fázis 4 -- Chat history és session kezelés

**Cél:** multi-turn conversation, history DB-ből töltve.

Feladatok:
- [ ] Session CRUD: create, list, get (üzenetekkel), delete
- [ ] Chat history beépítése a promptba (utolsó N üzenet)
- [ ] Session title auto-generálás (első kérdésből, Claude rövid hívással)
- [ ] Source selection per session (session.source_ids)
- [ ] `GET /api/sessions/{id}` -- üzenetek teljes listájával

Elfogadási kritériumok:
- Multi-turn conversation helyesen hivatkozik korábbi üzenetekre
- History DB-ből töltődik, nem memóriából
- Session törléskor üzenetek is törlődnek (CASCADE)

---

### Fázis 5 -- SSE streaming

**Cél:** valós idejű token megjelenítés a frontenden.

Feladatok:
- [ ] FastAPI `StreamingResponse` SSE implementáció
- [ ] Anthropic SDK `.stream()` token-onkénti olvasás
- [ ] Sources event a stream végén
- [ ] Frontend `EventSource` hook (`useSSE`)
- [ ] Graceful error handling (error event, kapcsolat megszakadás)
- [ ] Üzenet mentés stream befejezésekor

Elfogadási kritériumok:
- Tokenek valós időben jelennek meg a UI-ban
- Nincs teljes válasz pufferelés
- Hálózati hiba esetén a UI hibát jelez, nem fagy be

---

### Fázis 6 -- Frontend

**Cél:** teljes, használható UI.

Feladatok:
- [ ] `ChatView`: üzenetlista + streaming megjelenítés + input
- [ ] `SessionList`: sessionök listája, új session, törlés
- [ ] `SourcesView`: forrás lista státusszal, URL hozzáadás, törlés
- [ ] Source selection a chat indításakor
- [ ] Loading states, skeleton loaderek
- [ ] Error states, user-friendly hibaüzenetek
- [ ] Source citation megjelenítés az assistant üzenetekben
- [ ] Reszponzív layout (desktop-first, de mobilon is működik)

---

### Fázis 7 -- Code quality és tesztelés

**Cél:** production-ready minőség, teljes review.

Feladatok:
- [ ] Pytest coverage: 80%+ backend (főleg services + api)
- [ ] Vitest: useChat hook, useSSE hook, ChatInput, AddSourceForm
- [ ] `ruff check` + `ruff format` -- minden fájl tiszta
- [ ] `mypy --strict` -- 0 hiba
- [ ] Pre-commit hooks: ruff + mypy + pytest
- [ ] Minden TODO és FIXME eltüntetve
- [ ] README és DEVELOPMENT_SPEC final review

---

## Kódminőség szabályok

### Python (backend)

- Type hints minden publikus függvényen és metóduson
- Függvény max 50 sor -- ha hosszabb, bonts szét
- Fájl max 300 sor -- ha hosszabb, sub-modul kell
- Minden endpoint-nak van `response_model`
- Minden env var validálva startup-kor (pydantic-settings)
- Logging: structlog (JSON), print() tilos
- Saját exception osztályok a `app/exceptions.py`-ban
- ORM nincs -- raw asyncpg query-k, jól elnevezett, komment nélkül
- Async mindenütt ahol I/O van

### TypeScript (frontend)

- `strict: true` a tsconfig-ban, `any` tilos
- Komponens max 150 sor -- üzleti logika hookba kerül
- Hook max 100 sor -- split ha kell
- Minden API hívás typed, nincs implicit any response
- CSS: csak TailwindCSS osztályok, inline style tilos

---

## Tesztelési stratégia

### Backend (Pytest)

```
tests/
├── unit/
│   ├── test_chunker.py         # Text splitter logika
│   ├── test_retrieval.py       # Retrieval service (mock DB)
│   └── test_chat_service.py    # Prompt assembly, history truncation
└── integration/
    ├── test_api_sources.py     # Source CRUD endpoints
    ├── test_api_sessions.py    # Session + message endpoints
    └── conftest.py             # Test DB setup (real PostgreSQL)
```

- Integrációs tesztek valódi test DB-t használnak (nem mock)
- Ollama és Anthropic: mock (nem akarunk API hívást tesztekben)
- Minden fázis végén futtatva: `pytest --cov=app --cov-report=term-missing`

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

## Nyitott kérdések (döntés szükséges)

1. **Pre-seeded dokumentációk**: Melyik library dokumentációját indexeljük be alapból demóként? Javaslat: Tailwind CSS + React + TypeScript (mindhárom jól scrape-elhető, közel van a célközönséghez). Vagy más preferencia?

2. **Session source selection UX**: Session létrehozásakor kiválasztható legyen melyik forrás(ok)ból keresünk? Vagy az összes forrást mindig átkutatja? Az összes egyszerűbb, de több forrás esetén relevánsabb eredményt ad a szűrés.

---

## Függőségek

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

### Frontend (package.json)

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

## Változáskezelés

Ha a specifikáció változik:
1. Frissítsd a DEVELOPMENT_SPEC.md-t (jelöld mi változott és miért)
2. Érintett fázisok elfogadási kritériumait is frissítsd
3. Ha már kész kódot érint, nyiss egy újraírási feladatot -- ne patch-elj specen kívüli irányba
