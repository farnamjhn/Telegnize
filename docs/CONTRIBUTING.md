# Contributing to Telegnize

This is the guide for anyone extending Telegnize — human or agent. Read
[architecture.md](architecture.md) first for how the pieces fit together;
this document is about the rules to keep to while changing them.

---

## 1. Design principles

### Dependencies point inward
```
domain/          entities, lexicons, repository interfaces   — no frameworks
application/     services, DTOs, outbound ports              — no adapters
infrastructure/  FastAPI, SQLite, ijson, hazm, Laya          — the outside world
```

- `domain/` imports nothing but the standard library. No FastAPI, no Pydantic,
  no `sqlite3`, no `laya`.
- `application/` imports `domain` and its own ports. **It must not import
  `infrastructure`.** If a service needs something from the outside world, add
  an interface under `application/ports/` and implement it in `infrastructure/`.
- `infrastructure/` may import both. It is the only layer allowed to know a
  vendor's wire format.
- `infrastructure/api/container.py` is the single place the two halves are
  wired together. Nothing else constructs a repository or an adapter.

### Stream, never slurp
Telegram exports run to gigabytes. Use
`IExportReader.stream_messages(...)`, which yields batches. `json.load(f)` on
an upload path is a bug; `parse_file` exists for tests and small fixtures and
says so in its docstring.

### Derive once, in the entity
If a value can be computed from a message, it belongs as a property on
`Message` — one definition of what "a question" or "a cold closure" is. Values
analytics aggregates over are also written into columns at save time, so
queries can `SUM` them instead of loading rows.

### Aggregate in SQL
Analytics must not materialise a chat. Add an aggregate method to
`IMessageRepository` and implement it as a query. `iter_chat_timeline` exists
for the rare case that genuinely needs ordered rows, and it streams.

### Raise domain errors, not HTTP errors
Services raise from `domain/errors.py`. Routers do not catch them — the
handlers in `infrastructure/api/app.py` translate them. A service that imports
`fastapi` is in the wrong layer.

---

## 2. Getting started

Prerequisites: Python ≥ 3.12 and [`uv`](https://github.com/astral-sh/uv).

```bash
uv sync
uv run telegnize          # serves on http://127.0.0.1:8000, docs at /docs
```

```bash
uv run python -m unittest discover -s tests -t .
```

```bash
uv run ruff check . --fix
```

`tests/test_laya_engine.py` runs real model weights (~40s, needs network on
first run). Set `TELEGNIZE_SKIP_MODEL_TESTS=1` to skip it; everything that
depends on the engine is also covered against `tests/fakes.FakeDecisionEngine`.

---

## 3. Common changes

### Adding a decision question
1. Add a `DecisionQuestion` to `application/decision_questions.py`. A `choice`
   question needs at least two `criteria`; a `score` question needs at least
   two `levels`; a `noul` needs neither. These are validated on construction —
   a malformed question used to crash inside the model.
2. Cover it in `tests/test_decision_service.py` against the fake engine.

Callers can also override the question set per request by posting
`{"questions": {...}}`, which `questions_from_payload` turns into typed
questions.

### Adding an analytics metric
1. Add the field to `ChatAnalytics` and `ChatAnalyticsDTO`.
2. Add an aggregate method to `IMessageRepository` and implement it as a query
   in `SQLiteMessageRepository`. Do not add a Python loop over a whole chat.
3. Assert on it in `tests/test_analytics.py`, and on the query itself in
   `tests/test_sqlite_repositories.py`.

### Changing the database schema
1. Edit `infrastructure/persistence/schema.sql`. Every statement must be
   idempotent — it runs on every start.
2. Add an entry to `_MIGRATIONS` in
   `infrastructure/persistence/database.py` so databases created by an earlier
   version gain the column instead of failing with `no such column`.

### Adding a new export format
Implement `IExportReader` in `infrastructure/parser/` and select it in the
container. `IngestionService` does not change.

---

## 4. Conventions

- **Branches**: `feat/…`, `fix/…`, `perf/…`, `docs/…`.
- **Commits**: Conventional Commits, e.g. `feat(decisions): add escalation
  question`, `fix(parser): handle channel posts without actor_id`.
- **Text**: any ingested text goes through `ITextNormalizer.normalize`, and
  both the raw `text` and the `normalized_text` are stored. Persian and English
  are both first-class: recognise `؟` wherever you recognise `?`, and use
  `\w+` with Unicode for tokenisation.
- **Tests**: name what the behaviour is, not which method is called —
  `test_self_replies_do_not_count_as_responses`, not `test_latency_2`.

---

## 5. Troubleshooting

**Slow or rate-limited Laya downloads.** Set `HF_TOKEN`; weights cache in
`~/.cache/huggingface/hub/` after the first run. Set
`TELEGNIZE_PRELOAD_DECISION_ENGINE=1` to load them at startup instead of on the
first request.

**Ingestion memory.** Lower `TELEGNIZE_INGEST_BATCH_SIZE` (default 500).

**Persian question marks missed.** Use `Message.is_question` or
`TextNormalizer.is_question` rather than checking `"?"` by hand.
