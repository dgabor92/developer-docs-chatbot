# Developer Docs Chatbot

RAG-alapú chatbot fejlesztői dokumentációkhoz. Bármely dokumentációs oldalt be lehet indexelni URL alapján, utána természetes nyelvű kérdéseket lehet feltenni róla -- streaming válaszokkal, chat historyval és forráshivatkozásokkal.

## Stack

| Réteg | Technológia |
|---|---|
| Backend | Python 3.12 + FastAPI |
| LLM | Claude Haiku 4.5 (Anthropic SDK, SSE streaming) |
| Embeddings | Ollama (nomic-embed-text, lokális) |
| Adatbázis | PostgreSQL 16 + pgvector |
| Frontend | Vite + React + TypeScript + TailwindCSS |
| Konténerizáció | Docker + Docker Compose |
| Tesztelés | Pytest (backend) + Vitest (frontend) |

## Előfeltételek

- Docker + Docker Compose
- Ollama telepítve és futtatva lokálisan (`ollama pull nomic-embed-text`)
- Anthropic API kulcs

## Gyors start

```bash
# 1. Környezeti változók
cp .env.example .env
# Szerkeszd: ANTHROPIC_API_KEY=...

# 2. Szolgáltatások indítása
docker compose up -d

# 3. Adatbázis migrációk
docker compose exec api python -m app.db.migrate

# 4. Frontend dev szerver (fejlesztéshez)
cd frontend && npm install && npm run dev
```

Az API elérhető: http://localhost:8000  
A frontend elérhető: http://localhost:5173 (dev) / http://localhost:3000 (prod)  
API dokumentáció: http://localhost:8000/docs

## Dokumentáció indexelése

```bash
curl -X POST http://localhost:8000/api/sources \
  -H "Content-Type: application/json" \
  -d '{"name": "Tailwind CSS", "base_url": "https://tailwindcss.com/docs"}'
```

## Projekt struktúra

```
developer-docs-chatbot/
├── README.md
├── DEVELOPMENT_SPEC.md      # Részletes specifikáció és fejlesztési terv
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── app/
│       ├── api/             # FastAPI route handlerek
│       ├── services/        # Üzleti logika (ingestion, retrieval, chat)
│       ├── db/              # Adatbázis kapcsolat + migrációk
│       ├── models/          # Pydantic sémák
│       └── config.py        # Pydantic-settings konfiguráció
├── frontend/
│   ├── Dockerfile
│   └── src/
│       ├── components/      # React komponensek
│       ├── hooks/           # Custom hookok (useChat, useSources, useSSE)
│       ├── api/             # API kliens függvények
│       └── types/           # TypeScript típusok
└── docs/
    └── architecture.md      # Architektúra részletei
```

## Fejlesztési fázisok

Részletesen: [DEVELOPMENT_SPEC.md](DEVELOPMENT_SPEC.md)

1. **Infrastruktúra** -- Docker, FastAPI skeleton, DB schema
2. **Dokumentáció indexelés** -- web scraper, chunking, embeddings
3. **RAG core** -- pgvector keresés, Claude integráció
4. **Chat history** -- session kezelés, multi-turn conversation
5. **SSE streaming** -- valós idejű token megjelenítés
6. **Frontend** -- chat UI, source management
7. **Code quality** -- tesztek, lint, mypy, review

## AI Engineering Learning Path

Ez a projekt az AI Engineering learning path **6. fázisa**.

| Fázis | Projekt | Státusz |
|---|---|---|
| 1 | Claude API basics | Kész |
| 2 | Prompt engineering | Kész |
| 3 | RAG pipeline | Kész |
| 4 | FastAPI + pgvector RAG demo | Kész |
| 5 | LLM evaluation (RAGAS) | Kész |
| 6 | **Developer Docs Chatbot** | **Folyamatban** |
