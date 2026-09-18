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


settings = Settings()
