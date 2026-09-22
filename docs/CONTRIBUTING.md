# Contributing to Telegnize

Welcome to the **Telegnize** contribution guide! This document provides instructions and standards for both **human developers** and **autonomous AI agents** working on extending, optimizing, and maintaining Telegnize.

---

## 1. Project Overview & Design Philosophy

**Telegnize** is a high-performance Telegram chat export analyzer and intelligence engine.

### Core Architectural Principles
1. **Domain-Driven & Layered Architecture**: Strict separation of concerns:
   - `domain/`: Pure business entities (`Chat`, `Message`), lexicons, and repository interfaces (`IChatRepository`, `IMessageRepository`). Zero external framework dependencies.
   - `application/`: DTOs and orchestration services (`IngestionService`, `AnalyticsService`, `DecisionService`).
   - `infrastructure/`: Concrete adapters (FastAPI controllers, SQLite persistence, `ijson` streaming parser, Hazm/NLTK text normalizers, Laya System 1 decision engine).
2. **Stream-First Processing**: Never load full Telegram export JSONs into RAM with `json.load`. Always stream using `ijson.items(stream, "messages.item")` in configurable batches.
3. **System 1 Typed Decisions**: When classifying or routing text, use the **Laya** decision engine (`choice`, `score`, `noul`). Do not introduce slow token-by-token generative LLMs where a calibrated 33ms decision engine suffices.
4. **Multilingual by Default**: Treat Persian (`fa`) and English (`en`) as first-class citizens:
   - Persian text must be normalized through `hazm` (handling ZWNJ, half-spaces, Arabic/Persian character harmonization).
   - English text is normalized via `nltk` and regex.
   - Multilingual punctuation (such as `؟` vs `?`) must always be recognized.

---

## 2. Directory Structure

```
Telegnize/
├── application/
│   ├── dtos/                   # Data transfer objects for API and services
│   └── services/               # IngestionService, AnalyticsService, DecisionService
├── domain/
│   ├── models/                 # Chat, Message, Analysis domain entities
│   │   └── dict/lexicons.py    # Linguistic constants & low-investment tokens
│   └── repository/             # Repository interfaces (IChatRepository, etc.)
├── infrastructure/
│   ├── api/                    # FastAPI app, dependencies, and APIRouters
│   │   └── routers/            # chats.py, messages.py, analytics.py, decisions.py
│   ├── decision_engine/        # Laya engine wrapper & schematic typed questions
│   ├── nlp/                    # Multilingual text normalizer (hazm, nltk, re)
│   ├── parser/                 # Streaming JSON parser using ijson
│   ├── presistence/            # schema.sql (SQLite DDL)
│   └── repository/             # Concrete SQLite implementations with WAL mode
├── docs/                       # Architecture plans, walkthroughs, guides
├── tests/                      # Unit and integration test suite
├── example.json                # Reference Telegram chat export (~50k lines)
├── pyproject.toml              # Project dependencies managed by uv
└── main.py                     # API entrypoint
```

---

## 3. Getting Started & Development Workflow

### Prerequisites
- Python `>= 3.12`
- [`uv`](https://github.com/astral-sh/uv) (recommended Python package manager)

### Installation
```bash
# Clone the repository
git clone https://github.com/farnam-jhn/Telegnize.git
cd Telegnize

# Install dependencies using uv
uv sync
```

### Running the API Server
```bash
# Start server with auto-reload on port 8000
uv run uvicorn main:app --reload --port 8000
```
- Interactive OpenAPI documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/`

### Running the Test Suite
All contributions must pass all unit tests:
```bash
uv run python -m unittest discover tests
```

---

## 4. Guidelines for AI Agents (Agentic Instructions)

If you are an autonomous AI coding agent (e.g. Antigravity, Claude Engineer, Codex, etc.), follow these mandatory rules:

### 1. Memory & Streaming (`ijson`)
- Telegram exports can exceed several gigabytes. **NEVER** use `json.loads(file.read())` or `json.load(f)` on export uploads.
- Always use `TelegramJsonParser.stream_messages(...)` which utilizes `ijson.items(f, 'messages.item')` and yields batches of domain `Message` entities.

### 2. Working with the Laya Decision Engine
- Laya is imported as `from laya import Router`.
- When instantiating `Router`, avoid `preload=True` during cold start if memory is constrained. Use lazy loading or singleton access via `get_decision_engine()`.
- Router automatically chooses checkpoints:
  - English text (`latin`) -> `convaiinnovations/laya` (ModernBERT-large)
  - Non-Latin text (`arabic`/Persian) -> `convaiinnovations/laya` (mmBERT-base multilingual)
- Output formats:
  - `choice`: returns `choice` string, `probabilities` dict, and calibrated `confidence`.
  - `noul`: returns boolean true/false.
  - `score`: returns float score within range.
- Cache decision results in the `laya_decisions` table to avoid redundant model passes.

### 3. Database Schema Evolutions & Migrations
- SQLite runs in `WAL` mode (`PRAGMA journal_mode = WAL;`) and enforces foreign keys (`PRAGMA foreign_keys = ON;`).
- When introducing new columns, update `infrastructure/presistence/schema.sql`.
- **Always update `_init_db()` in `SQLiteMessageRepository` or `SQLiteChatRepository`** with `PRAGMA table_info(...)` checks and `ALTER TABLE ... ADD COLUMN ...` statements so existing SQLite files don't fail with `no such column` errors.

### 4. Text Normalization Pipeline
- Any new text field ingested into Telegnize must be passed through `TextNormalizer.get_instance().normalize(raw_text)`.
- Store both `raw_text` (unmodified source text) and `normalized_text` (processed by Hazm/NLTK).
- When writing regex for tokenization, use `\w+` with Unicode support so Persian words (`[\u0600-\u06FF]`) are counted correctly.

---

## 5. Guidelines for Human Developers

### Git Conventions
- **Branches**: Use descriptive branch names:
  - `feat/feature-name`
  - `fix/bug-description`
  - `perf/optimization-area`
- **Commits**: Follow Conventional Commits format:
  - `feat(laya): add intent detection question schema`
  - `fix(parser): handle missing actor_id in channel posts`
  - `test(analytics): add reply gap threshold verification`

### Adding a New Laya Question Schema
To add a new decision task (e.g. customer support escalation or sentiment classification):
1. Open `infrastructure/decision_engine/schemas.py`.
2. Define your typed question set:
   ```python
   NEW_TASK_QUESTIONS = {
       "escalate": {
           "type": "noul",
           "instructions": "Does this message require immediate human escalation?"
       }
   }
   ```
3. Expose the schema or helper method in `DecisionService`.
4. Add endpoint or query parameter in `infrastructure/api/routers/decisions.py`.
5. Add unit tests in `tests/test_laya_engine.py`.

### Adding New Analytics Metrics
1. Add new field(s) in `domain/models/analysis.py` and `application/dtos/analysis_dto.py`.
2. Implement calculation logic in `AnalyticsService.compute_chat_analytics()`.
3. Add assertions in `tests/test_analytics.py`.

---

## 6. Troubleshooting & FAQs

**Q: Hugging Face hub rate limits or slow downloads for Laya weights?**
> Set your Hugging Face token in the environment:
> ```bash
> export HF_TOKEN="hf_your_token_here"
> ```
> Weights are cached locally in `~/.cache/huggingface/hub/` after the first run.

**Q: Ingestion runs out of memory?**
> Ensure `batch_size` in `IngestionService.ingest_export` is kept between 200 and 1000 messages (default: 500).

**Q: Why are Persian question marks not detected?**
> Ensure you check for both `?` (ASCII) and `؟` (`\u061f` Persian/Arabic question mark) or use `msg.is_question`.

---

Thank you for contributing to Telegnize! 🚀
