from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.routes import (
    audit,
    auth,
    distribution,
    executions,
    llm,
    operations,
    organizations,
    reports,
    sources,
    users,
)
from app.core.config import Settings, get_settings

router = APIRouter()
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(sources.router)
router.include_router(reports.router)
router.include_router(executions.router)
router.include_router(users.router)
router.include_router(llm.router)
router.include_router(distribution.router)
router.include_router(audit.router)
router.include_router(operations.router)


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:  # noqa: B008
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )
