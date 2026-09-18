from enum import StrEnum


class OrganizationStatus(StrEnum):
    ACTIVE = "ATIVA"
    SUSPENDED = "SUSPENSA"
    ARCHIVED = "ARQUIVADA"


class LicenseStatus(StrEnum):
    ACTIVE = "ATIVA"
    SUSPENDED = "SUSPENSA"
    EXPIRED = "EXPIRADA"
    CANCELED = "CANCELADA"


class Role(StrEnum):
    PLATFORM_OPERATOR = "OPERADOR_PLATAFORMA"
    ORGANIZATION_ADMIN = "ADMIN_ORGANIZACAO"
    REPORT_CREATOR = "CRIADOR_RELATORIOS"
    VIEWER = "VISUALIZADOR"


class SourceType(StrEnum):
    POSTGRESQL = "BANCO_POSTGRESQL"
    ORACLE = "BANCO_ORACLE"
    SQLSERVER = "BANCO_SQLSERVER"
    CSV = "ARQUIVO_CSV"
    EXCEL = "ARQUIVO_EXCEL"
    JSON = "ARQUIVO_JSON"


class SourceStatus(StrEnum):
    DRAFT = "RASCUNHO"
    ACTIVE = "ATIVA"
    PAUSED = "PAUSADA"
    ERROR = "ERRO"
    REVOKED = "REVOGADA"


class SourceVersionStatus(StrEnum):
    VALID = "VALIDA"
    INVALID = "INVALIDA"
    EXPIRED = "EXPIRADA"


class DataClassification(StrEnum):
    PUBLIC = "PUBLICO"
    INTERNAL = "INTERNO"
    CONFIDENTIAL = "CONFIDENCIAL"
    SENSITIVE = "SENSIVEL"
    SECRET = "SECRETO"


class SensitivityAction(StrEnum):
    ALLOW = "PERMITIR"
    MASK = "MASCARAR"
    AGGREGATE = "AGREGAR"
    TOKENIZE = "TOKENIZAR"
    BLOCK = "BLOQUEAR"


class ReportStatus(StrEnum):
    DRAFT = "RASCUNHO"
    IN_REVIEW = "EM_REVISAO"
    PUBLISHED = "PUBLICADO"
    PAUSED = "PAUSADO"
    ARCHIVED = "ARQUIVADO"


class ReportVersionStatus(StrEnum):
    DRAFT = "RASCUNHO"
    IN_REVIEW = "EM_REVISAO"
    PUBLISHED = "PUBLICADO"
    ARCHIVED = "ARQUIVADO"


class ExecutionStatus(StrEnum):
    CREATED = "CRIADA"
    RUNNING = "EM_EXECUCAO"
    SUCCESS = "SUCESSO"
    SUCCESS_WITH_WARNINGS = "CONCLUIDA_COM_ALERTAS"
    FAILED = "FALHA"
    CANCELED = "CANCELADA"
    EXPIRED = "EXPIRADA"


class ArtifactType(StrEnum):
    SCREEN = "TELA"
    CSV = "CSV"
    XLSX = "XLSX"
    PDF = "PDF"
    CHART = "GRAFICO"


class GrantTargetType(StrEnum):
    USER = "USUARIO"
    ROLE = "PAPEL"
    ORGANIZATION = "ORGANIZACAO"


class DestinationType(StrEnum):
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"


class DestinationStatus(StrEnum):
    ACTIVE = "ATIVO"
    PAUSED = "PAUSADO"


class LlmProvider(StrEnum):
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    DEEPSEEK = "DEEPSEEK"
    GEMINI = "GEMINI"
    COPILOT = "COPILOT"


class AuditResult(StrEnum):
    SUCCESS = "SUCESSO"
    FAILURE = "FALHA"


class OutboxStatus(StrEnum):
    PENDING = "PENDENTE"
    SENT = "ENVIADO"
    FAILED = "FALHOU"
