"""Entry point for running the Telegnize API with uvicorn."""

import uvicorn

from infrastructure.api.app import app, configure_logging  # noqa: F401
from infrastructure.config import Settings


def main() -> None:
    settings = Settings()
    configure_logging(settings)
    uvicorn.run(
        "infrastructure.api.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
