"""FastAPI dependencies.

Each of these returns a collaborator from the process-wide
:class:`~infrastructure.api.container.Container`. Tests swap implementations by
overriding the container on the app, or these functions individually.
"""

from typing import Annotated

from fastapi import Depends, Request

from application.services.analytics_service import AnalyticsService
from application.services.assessment_service import AssessmentService
from application.services.chat_service import ChatService
from application.services.decision_service import DecisionService
from application.services.ingestion_service import IngestionService
from application.services.message_service import MessageService
from infrastructure.api.container import Container
from infrastructure.config import Settings


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_settings(container: Container = Depends(get_container)) -> Settings:
    return container.settings


def get_chat_service(container: Container = Depends(get_container)) -> ChatService:
    return container.chat_service


def get_message_service(
    container: Container = Depends(get_container),
) -> MessageService:
    return container.message_service


def get_ingestion_service(
    container: Container = Depends(get_container),
) -> IngestionService:
    return container.ingestion_service


def get_analytics_service(
    container: Container = Depends(get_container),
) -> AnalyticsService:
    return container.analytics_service


def get_assessment_service(
    container: Container = Depends(get_container),
) -> AssessmentService:
    return container.assessment_service


def get_decision_service(
    container: Container = Depends(get_container),
) -> DecisionService:
    return container.decision_service


ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
DecisionServiceDep = Annotated[DecisionService, Depends(get_decision_service)]
AssessmentServiceDep = Annotated[AssessmentService, Depends(get_assessment_service)]
