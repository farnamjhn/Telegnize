# Architecture

Telegnize is a layered application. Dependencies point inward: `infrastructure`
knows about `application` and `domain`, `application` knows about `domain`, and
`domain` knows about nothing but the standard library.

```mermaid
flowchart TB
    subgraph infra ["infrastructure/ — adapters"]
        API["FastAPI routers"]
        Parser["TelegramJsonParser (ijson)"]
        Norm["TextNormalizer (hazm)"]
        Laya["LayaDecisionEngine"]
        SQLite["SQLite repositories"]
    end

    subgraph app ["application/ — use cases"]
        Services["Ingestion · Analytics · Decision · Message · Chat services"]
        Ports["ports: IExportReader · ITextNormalizer · IDecisionEngine"]
        DTOs["DTOs"]
    end

    subgraph dom ["domain/ — business rules"]
        Entities["Chat · Message · Decision · Language"]
        Repos["IChatRepository · IMessageRepository · IDecisionRepository"]
        Errors["TelegnizeError hierarchy"]
    end

    API --> Services
    Services --> Ports
    Services --> Repos
    Services --> DTOs
    DTOs --> Entities
    Parser -.implements.-> Ports
    Norm -.implements.-> Ports
    Laya -.implements.-> Ports
    SQLite -.implements.-> Repos
```

## Importing an export

```mermaid
sequenceDiagram
    participant Client
    participant Router as chats router
    participant Service as IngestionService
    participant Reader as TelegramJsonParser
    participant Repo as SQLite repositories

    Client->>Router: POST /api/chats/upload
    Router->>Service: ingest_export(stream)
    Service->>Reader: extract_metadata(stream)
    Reader-->>Service: ChatMetadata
    Service->>Repo: save(Chat)
    loop one batch at a time
        Service->>Reader: next batch of Messages
        Reader-->>Service: [Message] (normalized, language tagged)
        Service->>Repo: save_batch(batch)
    end
    Service->>Repo: update_message_count
    Service-->>Client: ImportSummaryDTO
```

The whole document is never in memory: `ijson` yields one message at a time and
the parser groups them into batches of `TELEGNIZE_INGEST_BATCH_SIZE`.

## Where each decision lives

**Derived values are computed once, at write time.** `word_count`,
`char_count`, `is_question`, and `is_cold_closure` are properties on the
`Message` entity — one definition — and are written into columns as messages are
stored. Analytics then reads them with `SUM(...)` instead of loading rows into
Python, so the cost of analysing a chat does not grow with its size.

**Response latency is SQL.** A message that replies to a message still in the
chat is timed against that parent; otherwise it is timed against whatever came
directly before it. A `LAG()` window function and a self-join express both
cases in one query, with the two time windows passed as parameters rather than
buried as literals.

**One `Database`, many repositories.** `infrastructure/persistence/database.py`
owns the connection policy — WAL, foreign keys, busy timeout — and applies the
schema once. Repositories borrow a connection per operation, which makes them
safe to share across FastAPI's worker threads and lets an in-memory database be
shared by every repository in a test.

**Ports keep the model swappable.** `application/ports/` defines what the
services need; `infrastructure/` supplies it. `DecisionService` works against
`IDecisionEngine`, which is why the test suite can exercise the whole decision
flow against a fake in milliseconds and still keep one integration test against
real weights.

**Errors are domain objects.** Services raise `ChatNotFoundError`,
`MessageNotFoundError`, `InvalidExportError`, `DecisionEngineError`; the
translation to HTTP status codes happens once, in
`infrastructure/api/app.py`. No service imports FastAPI.

## Typed decisions

A question is a `DecisionQuestion`: a key, a type (`choice`, `score`, `noul`),
instructions, and the criteria or levels that define its answer space. The Laya
adapter is the only code that knows Laya's wire format — it renders questions
into Laya's schema and decodes answers back into `EngineAnswer`, including
turning Laya's `noul` probability into the boolean the caller asked for while
keeping the probability alongside it.

Answers are cached in the `decisions` table keyed by (target, question), so
re-asking is free and changing one question does not invalidate the others.
