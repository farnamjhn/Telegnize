# Telegnize

Telegnize imports Telegram chat exports, normalizes Persian and English text,
and reports what the conversation looked like — who carried it, how fast people
answered each other, when they talked — alongside typed decisions from the
[Laya](https://pypi.org/project/laya/) System 1 engine.

Exports are read as a stream, so a multi-gigabyte file imports in the same
memory footprint as a small one.

## Quick start

```bash
uv sync
uv run telegnize
```

The API then serves on `http://127.0.0.1:8000`, with interactive documentation
at `/docs`.

To bring up the web interface as well, in a second shell:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

The UI serves on `http://localhost:3000` and proxies `/api` to the API on port
8000, so no CORS configuration is needed. Point it somewhere else with
`TELEGNIZE_API=http://host:port npm --prefix frontend run dev`.

Or drive it from the command line. Import an export and look at it:

```bash
curl -X POST localhost:8000/api/chats/import-local \
  -H 'Content-Type: application/json' -d '{"file_path": "export.json"}'
```

```bash
curl localhost:8000/api/analytics/1
```

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/chats/upload` | Import an uploaded export |
| `POST` | `/api/chats/import-local` | Import an export already on the server |
| `GET` | `/api/chats` | List imported chats |
| `GET` `DELETE` | `/api/chats/{id}` | Read or delete one chat |
| `GET` `POST` | `/api/messages` | Query messages, or store one |
| `GET` | `/api/analytics/{chat_id}` | [Behavioural profile](docs/analytics.md) of a chat |
| `POST` `GET` | `/api/decisions/messages/{id}` | Evaluate a message, or read the cache |
| `POST` `GET` | `/api/decisions/chats/{id}` | Evaluate a conversation window |
| `POST` `GET` | `/api/assessments/{chat_id}` | Run a [relational assessment](docs/analytics.md) pass, or read it |
| `POST` | `/api/chats/{chat_id}/rederive` | Recompute derived columns from the text already stored |
| `POST` | `/api/decisions/custom` | Ask arbitrary typed questions |
| `GET` | `/api/health` | Service and dependency status |

## Interface

`frontend/` is a React + TypeScript app built with Vite, and the only consumer
of the API that ships in this repository. It covers the same ground the
endpoints do: importing exports, the behavioural profile of a chat, a message
browser that lays Persian out right-to-left, and typed decisions with the
probability the engine assigned to every alternative.

Counted and classified figures are kept apart the way
[docs/analytics.md](docs/analytics.md) keeps them apart — **Analytics** for what
was counted, **Assessment** for what a model read. The participant tables in
both follow that document's groups, each carrying its caveat, and the
assessment pass is driven one page at a time from the UI so a run is always a
deliberate choice rather than something a button starts by accident.

```bash
npm --prefix frontend run dev        # http://localhost:3000
npm --prefix frontend run build      # static bundle in frontend/dist
npm --prefix frontend run typecheck
```

A production build reads `VITE_API_BASE` for the API origin; leaving it unset
makes the bundle call `/api` on whatever host serves it.

## Architecture

Three layers, with dependencies pointing inward:

```
domain/          entities, lexicons, repository interfaces   — no frameworks
application/     services, DTOs, outbound ports              — no adapters
infrastructure/  FastAPI, SQLite, ijson, hazm, Laya          — the outside world
frontend/        React + Vite UI                             — an API client
```

`application/ports/` holds the interfaces the services depend on — an export
reader, a text normalizer, a decision engine — and `infrastructure/` supplies
the implementations. `infrastructure/api/container.py` is the one place the two
halves are wired together.

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the design rules and
[docs/architecture.md](docs/architecture.md) for how a request flows through
the system.

## Analytics

**Counted** — exact arithmetic over timestamps and words. Per participant: what
hours they keep and how fast they answer while the conversation is live, who
opens and closes it and who revives it after days of nothing, how they hold the
floor (bursts, last word, messages that crossed in flight), what their
messages are made of (vocabulary, media, voice, links), and what their wording
carries — affection, apology, gratitude, absolutism, hedging, questions asked,
"we" against "I". Chat-wide: the rhythm of sittings and silences, how evenly
the conversation is shared, and how far the two participants' function-word use
converges.

**Classified** — a model's reading of each message, under
`/api/assessments`: emotional valence and the positive-to-negative ratio, bids
for connection and whether the reply engaged with them, friction by kind,
repair attempts, sarcasm, and open questions. This runs a model over every
message on CPU and is expensive — time a small page before starting a long run
— so it is paged and resumable, and every figure is reported against how much
of the chat it covers.

These are observations about a transcript, not measurements of a relationship.
[docs/analytics.md](docs/analytics.md) sets out what each figure means, what it
cannot tell you, and how to tune the thresholds behind it.

## Configuration

Every setting is an environment variable prefixed `TELEGNIZE_`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `TELEGNIZE_DB_PATH` | `telegnize.sqlite` | SQLite file, or `:memory:` |
| `TELEGNIZE_HOST` | `127.0.0.1` | Bind address |
| `TELEGNIZE_PORT` | `8000` | Bind port |
| `TELEGNIZE_LOG_LEVEL` | `INFO` | Root log level |
| `TELEGNIZE_INGEST_BATCH_SIZE` | `500` | Messages per insert transaction |
| `TELEGNIZE_MAX_PAGE_SIZE` | `1000` | Ceiling on a list request |
| `TELEGNIZE_REPLY_WINDOW_SECONDS` | `86400` | Gap still counted as answering a reply |
| `TELEGNIZE_TURN_WINDOW_SECONDS` | `21600` | Gap still counted as answering a turn |
| `TELEGNIZE_SESSION_GAP_SECONDS` | `21600` | Silence that starts a new session |
| `TELEGNIZE_UPTAKE_WINDOW_SECONDS` | `3600` | How long a question stays live |
| `TELEGNIZE_ACTIVE_SESSION_SECONDS` | `7200` | Gap still counted as a reply inside a live conversation |
| `TELEGNIZE_LAST_WORD_GAP_SECONDS` | `10800` | Silence after which the message before it ended the conversation |
| `TELEGNIZE_SILENCE_SECONDS` | `172800` | Silence after which the conversation counts as stopped |
| `TELEGNIZE_COLLISION_SECONDS` | `30` | Gap inside which two messages count as written at once |
| `TELEGNIZE_BURST_FLOOR` | `3` | Messages in one turn before it counts as a burst |
| `TELEGNIZE_ASSESSMENT_PAGE_SIZE` | `25` | Messages assessed per call |
| `TELEGNIZE_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins — the default is where `frontend/` dev-serves |
| `TELEGNIZE_PRELOAD_DECISION_ENGINE` | `0` | `1` loads model weights at startup |
| `TELEGNIZE_RESIDENT_CHECKPOINTS` | `2` | Checkpoints held in memory at once — below 2, a chat that mixes scripts rebuilds one per switch |
| `TELEGNIZE_DECISION_CACHE_ENTRIES` | `10000` | Engine answers memoised, so repeated text is read once; `0` disables |

## Tests

```bash
uv run python -m unittest discover -s tests -t .
```

`tests/test_laya_engine.py` downloads and runs real model weights, so it is
skipped by default. Set `TELEGNIZE_SKIP_MODEL_TESTS=0` to run it deliberately:

```bash
TELEGNIZE_SKIP_MODEL_TESTS=0 uv run python -m unittest discover -s tests -t .
```
