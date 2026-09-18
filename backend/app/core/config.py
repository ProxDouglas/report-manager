from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração validada do processo da API ou do worker."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Plataforma de Relatórios"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg://report_manager:report_manager@localhost:5432/report_manager"
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout_seconds: int = 30

    secret_key: SecretStr = SecretStr("local-development-only-change-me")
    cors_origins: str = "http://localhost:5173"
    session_cookie_name: str = "report_manager_session"
    session_ttl_hours: int = 12
    auth_max_login_attempts: int = 5
    auth_login_window_seconds: int = 900
    allow_bootstrap: bool = False
    bootstrap_operator_email: str = "operator@example.com"
    bootstrap_operator_password: SecretStr = SecretStr("")

    retention_report_versions_years: int = 3
    retention_artifacts_years: int = 3
    retention_source_snapshots_years: int = 3
    retention_execution_logs_years: int = 3
    retention_audit_logs_years: int = 3

    execution_timeout_seconds: int = 1800
    execution_max_rows: int = 1_000_000
    execution_max_result_bytes: int = 524_288_000
    source_max_file_bytes: int = 104_857_600
    artifact_max_bytes: int = 524_288_000
    artifact_storage_backend: str = "postgres"
    source_connection_timeout_seconds: int = 30
    source_max_json_depth: int = 20
    source_max_columns: int = 500
    source_max_sheet_rows: int = 1_000_000
    public_source_ips_only: bool = True
    max_users_per_organization: int = 50
    max_concurrent_executions_per_organization: int = 2
    distribution_max_retries: int = 3
    webhook_timeout_seconds: int = 30
    worker_readiness_timeout_seconds: int = 90
    queue_stall_seconds: int = 900
    artifact_storage_warning_bytes: int = 4_000_000_000
    license_expiration_warning_days: int = 30

    sandbox_cpu_limit: int = 2
    sandbox_memory_mb: int = 2048
    sandbox_max_retries: int = 3
    sandbox_network_mode: str = "none"
    sandbox_image: str = "report-manager-sandbox:local"
    sandbox_read_only: bool = True
    sandbox_workspace: str = "/tmp/report-manager-sandbox"

    smtp_host: str = "smtp.example.com"
    smtp_port: int = 587
    smtp_username: str = "report-manager"
    smtp_password_secret_ref: str = "vault://platform/smtp/report-manager"
    smtp_use_tls: bool = True
    smtp_from_email: str = "reports@example.com"
    smtp_from_name: str = "Plataforma de Relatórios"
    smtp_timeout_seconds: int = 30

    vault_addr: str = "http://localhost:8200"
    vault_token: SecretStr = SecretStr("dev-only-token")

    @field_validator(
        "database_pool_size",
        "database_max_overflow",
        "database_pool_timeout_seconds",
        "session_ttl_hours",
        "auth_max_login_attempts",
        "auth_login_window_seconds",
        "retention_report_versions_years",
        "retention_artifacts_years",
        "retention_source_snapshots_years",
        "retention_execution_logs_years",
        "retention_audit_logs_years",
        "execution_timeout_seconds",
        "execution_max_rows",
        "execution_max_result_bytes",
        "source_max_file_bytes",
        "artifact_max_bytes",
        "source_connection_timeout_seconds",
        "source_max_json_depth",
        "source_max_columns",
        "source_max_sheet_rows",
        "max_users_per_organization",
        "max_concurrent_executions_per_organization",
        "distribution_max_retries",
        "webhook_timeout_seconds",
        "worker_readiness_timeout_seconds",
        "queue_stall_seconds",
        "artifact_storage_warning_bytes",
        "license_expiration_warning_days",
        "sandbox_cpu_limit",
        "sandbox_memory_mb",
        "sandbox_max_retries",
        "smtp_port",
        "smtp_timeout_seconds",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("o valor deve ser maior que zero")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
