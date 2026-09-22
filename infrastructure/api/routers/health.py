"""Liveness and readiness endpoints."""

from typing import Any

from fastapi import APIRouter

from infrastructure.api.dependencies import ContainerDep

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Service and dependency status")
def health(container: ContainerDep) -> dict[str, Any]:
    engine = container.decision_engine
    return {
        "status": "ok",
        "app": "Telegnize API",
        "database": container.settings.db_path,
        "decision_engine": engine.describe(),
    }
