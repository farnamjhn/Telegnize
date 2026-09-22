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
2. To have it run over a whole chat, add it to `ASSESSMENT_QUESTIONS` and
   aggregate it in `AssessmentService._participant`. Remember that each
   question adds inference time to every message in every pass.
3. Cover it in `tests/test_decision_service.py` or `tests/test_assessment.py`
   against `FakeDecisionEngine`, which can be given forced answers. Never add a
   test that loads real weights outside `tests/test_laya_engine.py`.

### Writing about a classified metric
Metrics the model produces carry more interpretive weight than counted ones,
and several borrow vocabulary from clinical research. Two rules:

- **Name what was actually measured.** "Messages the classifier read as
  negative", not "negative messages".
- **Do not import a threshold with the vocabulary.** Borrowing Gottman's
  positive-to-negative ratio does not license quoting his 5:1 figure as a
  target: that number came from coded observation of couples in a lab against
  measured outcomes, and nothing here reproduces that. Say so wherever the
  metric is documented.

Callers can also override the question set per request by posting
`{"questions": {...}}`, which `questions_from_payload` turns into typed
questions.

### Adding an analytics metric
1. Add the field to the matching read model in `domain/models/analysis.py`
   (`Responsiveness`, `Engagement`, `Expression`, `ConversationRhythm`,
   `Balance`) and to its DTO.
2. Add an aggregate method to `IMessageRepository` and implement it as a query
   in `SQLiteMessageRepository`. Do not add a Python loop over a whole chat.
3. Assert on it in `tests/test_analytics.py`, and on the query itself in
   `tests/test_sqlite_repositories.py`.
4. Document it in `docs/analytics.md`, including what it cannot tell you.

Two rules specific to this area:

- **Normalise for verbosity.** A raw count of anything mostly measures who
  writes more. Report a rate per thousand words, or a share, alongside it.
- **Check the metric does not saturate.** A threshold generous enough that
  every participant scores 100% carries no information. Try it against a real
  export before settling on the window.

### Adding a word marker
Add the token to the right set in `domain/models/lexicons.py`, add a counter to
`MessageMarkers` and a column if it is a new category, and add the migration
entry. Keep the module docstring's honesty note intact: these lists describe
wording, and the documentation must not let them read as a score of anyone.

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

## 4. The frontend

`frontend/` is a React + TypeScript app (Vite). It is an API client and
nothing more — no analysis happens there. If the UI needs a number, add it to
the analytics aggregate and serve it; do not compute it over a page of
messages in the browser.

```
src/lib/        api client, DTO mirrors, formatting, hooks
src/components/ primitives, the app shell, the chart layer
src/views/      one file per section
src/styles/     tokens.css (the theme) + base.css (everything else)
```

- **Types mirror the DTOs.** `src/lib/types.ts` is the wire shape of
  `application/dtos/`. Change a DTO, change that file — `npm --prefix frontend
  run typecheck` then names every view that has drifted.
- **The participant tables follow the DTO groups.** Volume, responsiveness,
  engagement and expression are one table each behind a toggle, mirroring
  `ParticipantStatsDTO`'s nesting and the sections of
  [analytics.md](analytics.md). A new metric goes in the group it belongs to,
  and that document's caveat goes into the table's subtitle — these figures are
  easy to over-read, and the UI must not help.
- **A metric with no data says so.** Marker columns are written at ingest, so a
  chat imported before a metric existed reads as all-zero. The Expression table
  detects that and explains it rather than showing a wall of zeros.
- **Plain CSS, one dark theme.** Every colour, radius and duration is a custom
  property in `tokens.css`; components reference roles, never raw hex. There is
  no CSS framework and no component library — a new widget is a class in
  `base.css`.
- **Charts follow the house rules.** A single-series chart is one colour with
  no legend (the card title names it). Categorical charts use the three fixed
  series slots in order — white, orange, grey — and fold the tail into
  "+N more"; never add a fourth. The slots separate by lightness rather than
  hue, which survives colour blindness but makes the swatch weak identity, so a
  legend and a table view are mandatory. Bars cap at 24px with a rounded
  data-end and gridlines are solid hairlines.
- **Orange is reserved.** It is the alarm end of a scale — errors, destructive
  actions, low confidence — and the only chromatic colour in the system. Using
  it decoratively costs it its meaning.
- **Persian is first-class here too.** Message text gets its direction from
  `directionOf`, which reads the language tag and falls back to the script.
- **Filters live in one row above what they scope**, never inside a card, and a
  refetch holds the previous render at reduced opacity rather than flashing a
  skeleton.

```bash
npm --prefix frontend run typecheck
```

---

## 5. Conventions

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

## 6. Troubleshooting

**Slow or rate-limited Laya downloads.** Set `HF_TOKEN`; weights cache in
`~/.cache/huggingface/hub/` after the first run. Set
`TELEGNIZE_PRELOAD_DECISION_ENGINE=1` to load them at startup instead of on the
first request.

**Ingestion memory.** Lower `TELEGNIZE_INGEST_BATCH_SIZE` (default 500).

**Persian question marks missed.** Use `Message.is_question` or
`TextNormalizer.is_question` rather than checking `"?"` by hand.
