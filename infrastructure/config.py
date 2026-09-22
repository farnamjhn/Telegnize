"""Runtime configuration, read once from the environment.

Every tunable lives here rather than as a module-level ``os.getenv`` next to
the code that happens to need it, so the full surface is visible in one place
and tests can build a ``Settings`` object directly.
"""

import os
from dataclasses import dataclass, field

ENV_PREFIX = "TELEGNIZE_"

DEFAULT_DB_PATH = "telegnize.sqlite"


def _env(name: str, default: str) -> str:
    return os.getenv(f"{ENV_PREFIX}{name}", default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(f"{ENV_PREFIX}{name}")
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(
            f"{ENV_PREFIX}{name} must be an integer, got {raw!r}."
        ) from error


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(f"{ENV_PREFIX}{name}")
    if raw is None:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    """Everything the process needs to know about its environment."""

    db_path: str = field(default_factory=lambda: _env("DB_PATH", DEFAULT_DB_PATH))
    host: str = field(default_factory=lambda: _env("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("PORT", 8000))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    ingest_batch_size: int = field(
        default_factory=lambda: _env_int("INGEST_BATCH_SIZE", 500)
    )
    #: Maximum messages a single list request may return.
    max_page_size: int = field(default_factory=lambda: _env_int("MAX_PAGE_SIZE", 1000))
    #: Browser origins allowed to call the API. Defaults to local development
    #: only: a public wildcard is a deployment decision, not a default.
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list(
            "CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"]
        )
    )
    # --- analysis windows -------------------------------------------------
    # What counts as answering, as one sitting, or as a question still being
    # live depends on the conversation: colleagues and a couple keep very
    # different rhythms, so these are settings rather than constants.
    #: Longest gap still counted as answering an explicit reply, in seconds.
    reply_window_seconds: int = field(
        default_factory=lambda: _env_int("REPLY_WINDOW_SECONDS", 24 * 60 * 60)
    )
    #: Longest gap still counted as answering the previous turn, in seconds.
    turn_window_seconds: int = field(
        default_factory=lambda: _env_int("TURN_WINDOW_SECONDS", 6 * 60 * 60)
    )
    #: Silence long enough to treat what follows as a new conversation.
    session_gap_seconds: int = field(
        default_factory=lambda: _env_int("SESSION_GAP_SECONDS", 6 * 60 * 60)
    )
    #: How long a question stays live for the purpose of counting it answered.
    uptake_window_seconds: int = field(
        default_factory=lambda: _env_int("UPTAKE_WINDOW_SECONDS", 60 * 60)
    )

    #: Load the decision-engine checkpoints at startup instead of on first use.
    preload_decision_engine: bool = field(
        default_factory=lambda: _env("PRELOAD_DECISION_ENGINE", "0") == "1"
    )
