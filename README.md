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

Import an export and look at it:

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
| `GET` | `/api/analytics/{chat_id}` | Behavioural profile of a chat |
| `POST` `GET` | `/api/decisions/messages/{id}` | Evaluate a message, or read the cache |
| `POST` `GET` | `/api/decisions/chats/{id}` | Evaluate a conversation window |
| `POST` | `/api/decisions/custom` | Ask arbitrary typed questions |
| `GET` | `/api/health` | Service and dependency status |

## Architecture

Three layers, with dependencies pointing inward:

```
domain/          entities, lexicons, repository interfaces   — no frameworks
application/     services, DTOs, outbound ports              — no adapters
infrastructure/  FastAPI, SQLite, ijson, hazm, Laya          — the outside world
```

`application/ports/` holds the interfaces the services depend on — an export
reader, a text normalizer, a decision engine — and `infrastructure/` supplies
the implementations. `infrastructure/api/container.py` is the one place the two
halves are wired together.

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for the design rules and
[docs/architecture.md](docs/architecture.md) for how a request flows through
the system.

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
| `TELEGNIZE_CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated browser origins |
| `TELEGNIZE_PRELOAD_DECISION_ENGINE` | `0` | `1` loads model weights at startup |

## Tests

```bash
uv run python -m unittest discover -s tests -t .
```

`tests/test_laya_engine.py` downloads and runs real model weights. Skip it when
working offline:

```bash
TELEGNIZE_SKIP_MODEL_TESTS=1 uv run python -m unittest discover -s tests -t .
```
