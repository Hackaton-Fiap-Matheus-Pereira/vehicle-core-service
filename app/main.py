import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.health import router as health_router
from app.api.router import api_router
from app.api.v1.internal import router as internal_router
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import create_engine, create_session_factory
from app.services.sales_client import SalesClient


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    logging.basicConfig(
        level=resolved_settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    engine = create_engine(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    application = FastAPI(
        title="Vehicle Core Service",
        version="1.0.0",
        description="Cadastro canônico de veículos e gateway de pagamentos.",
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.engine = engine
    application.state.session_factory = create_session_factory(engine)
    application.state.sales_client = SalesClient(
        base_url=resolved_settings.sales_service_url,
        service_token=resolved_settings.service_token.get_secret_value(),
        timeout_seconds=resolved_settings.sales_service_timeout_seconds,
    )

    @application.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        error = {"code": exc.code, "message": exc.message}
        if exc.details is not None:
            error["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content={"error": error})

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "location": list(error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dados de entrada inválidos",
                    "details": details,
                }
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def handle_database_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Não foi possível acessar o banco de dados",
                }
            },
        )

    application.include_router(health_router)
    application.include_router(api_router)
    application.include_router(internal_router)
    return application


app = create_app()
