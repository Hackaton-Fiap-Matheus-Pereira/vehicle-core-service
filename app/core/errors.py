from typing import Any


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class AuthenticationError(AppError):
    def __init__(self, message: str = "Credenciais inválidas") -> None:
        super().__init__(status_code=401, code="AUTHENTICATION_REQUIRED", message=message)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Acesso negado") -> None:
        super().__init__(status_code=403, code="FORBIDDEN", message=message)


class ConflictError(AppError):
    def __init__(self, message: str, *, code: str = "CONFLICT") -> None:
        super().__init__(status_code=409, code=code, message=message)


class NotFoundError(AppError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            status_code=404,
            code="NOT_FOUND",
            message=f"{resource} não encontrado",
        )


class SalesServiceError(AppError):
    def __init__(
        self,
        message: str = "O serviço de vendas está indisponível",
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(
            status_code=503,
            code="SALES_SERVICE_UNAVAILABLE",
            message=message,
            details=details,
        )
