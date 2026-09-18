from app.api.router import health
from app.core.config import get_settings


def test_health_returns_service_status() -> None:
    response = health(get_settings())

    assert response.status == "ok"
    assert response.service == "Plataforma de Relatórios"
