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

    app_port: int = 8000
    datasets_directory: str = "datasets"
    max_upload_bytes: int = 25 * 1024 * 1024
    max_upload_files: int = 10
    max_batch_upload_bytes: int = 100 * 1024 * 1024
    max_dataset_rows: int = 100000
    max_dataset_columns: int = 500
    dataset_retention_seconds: int = 7200


@lru_cache
def get_settings() -> Settings:
    return Settings()
