from fastapi import APIRouter, Depends, HTTPException

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    get_container,
)


router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/database/health")
def database_health(
    container: ApplicationContainer = Depends(get_container),
) -> dict[str, str]:
    try:
        container.analytics_repository.test_connection()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao conectar ao banco: {error}",
        ) from error

    return {
        "database": container.analytics_repository.active_database().value,
        "status": "connected",
    }
