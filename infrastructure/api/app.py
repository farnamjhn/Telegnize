"""FastAPI application factory and error translation.

``create_app`` builds a fully wired application; the module-level ``app`` is
the instance uvicorn serves. Tests build their own with a different
:class:`Container`, so nothing here needs to be reconfigured after import.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from application.ports.decision_engine import DecisionEngineError
from domain.errors import InvalidExportError, NotFoundError
from infrastructure.api.container import Container
from infrastructure.api.routers import (
    analytics,
    assessments,
    chats,
    decisions,
    health,
    messages,
)
from infrastructure.config import Settings

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

API_PREFIX = "/api"

DESCRIPTION = (
    "Imports Telegram chat exports, normalizes Persian and English text, and "
    "reports behavioural analytics and typed decisions about a conversation."
)


def configure_logging(settings: Settings | None = None) -> None:
    """Sets up logging for a process that runs Telegnize.

    The entry point calls this, not ``create_app``: an application object
    embedded in someone else's process should not reconfigure their logging.
    """
    settings = settings or Settings()
    logging.basicConfig(level=settings.log_level, format=LOG_FORMAT)


def create_app(container: Container | None = None) -> FastAPI:
    """Builds an application around ``container`` (a default one if omitted)."""
    container = container or Container()
    settings = container.settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.container = container
        logger.info("Telegnize starting against database %s.", settings.db_path)
        try:
            yield
        finally:
            container.close()

    app = FastAPI(
        title="Telegnize API",
        version="0.3.0",
        description=DESCRIPTION,
        lifespan=lifespan,
    )
    # Available before startup too, so TestClient requests outside the lifespan
    # and health checks during boot both resolve.
    app.state.container = container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    for router in (
        chats.router,
        messages.router,
        analytics.router,
        decisions.router,
        assessments.router,
    ):
        app.include_router(router, prefix=API_PREFIX)
    app.include_router(health.router, prefix=API_PREFIX)

    _register_error_handlers(app)

    @app.get("/", tags=["Health"], summary="Service identity")
    def root() -> dict:
        return {"status": "ok", "app": "Telegnize API", "docs": "/docs"}

    return app


def _register_error_handlers(app: FastAPI) -> None:
    """Maps application errors onto HTTP responses.

    Services raise domain errors and never import FastAPI; the translation to
    status codes happens once, here.
    """

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)}
        )

    @app.exception_handler(InvalidExportError)
    async def _invalid_export(_: Request, error: InvalidExportError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(error)}
        )

    @app.exception_handler(DecisionEngineError)
    async def _engine_failure(_: Request, error: DecisionEngineError) -> JSONResponse:
        logger.error("Decision engine failure: %s", error)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "The decision engine could not answer this request."},
        )


app = create_app()
