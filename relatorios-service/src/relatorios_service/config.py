from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str
    llm_model: str
    openai_base_url: str | None = None

    database_type: str = "postgres"
    database_url: str | None = None

    reports_directory: str = "reports"
    max_analysis_rows: int = 10000
    app_port: int = 8000
    datasets_directory: str = "datasets"
    max_upload_bytes: int = 25 * 1024 * 1024
    max_dataset_rows: int = 100000
    max_dataset_columns: int = 500
    dataset_retention_seconds: int = 7200

    audit_log_enabled: bool = True
    audit_log_file: str = "logs/auditoria.txt"


@lru_cache
def get_settings() -> Settings:
    return Settings()
