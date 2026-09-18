from typing import Any


class DomainError(Exception):
    """Erro previsível que pode ser apresentado sem detalhes internos."""

    def __init__(
        self, message: str, code: str = "domain_error", status_code: int = 400, details: Any = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundError(DomainError):
    def __init__(self, message: str = "Recurso não encontrado."):
        super().__init__(message, "not_found", 404)


class ForbiddenError(DomainError):
    def __init__(self, message: str = "Acesso não permitido."):
        super().__init__(message, "forbidden", 403)


class UnauthorizedError(DomainError):
    def __init__(self, message: str = "Não autenticado."):
        super().__init__(message, "unauthorized", 401)


class ConflictError(DomainError):
    def __init__(self, message: str = "Conflito de estado."):
        super().__init__(message, "conflict", 409)


class ValidationError(DomainError):
    def __init__(self, message: str = "Os dados informados são inválidos."):
        super().__init__(message, "validation_error", 422)
