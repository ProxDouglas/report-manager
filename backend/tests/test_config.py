import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_parse_multiple_cors_origins() -> None:
    settings = Settings(cors_origins="http://localhost:5173, http://localhost:4173")

    assert settings.cors_origin_list == ["http://localhost:5173", "http://localhost:4173"]


def test_settings_reject_non_positive_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(execution_timeout_seconds=0)
