"""Aplicación FastAPI.

    uvicorn smartcuts.interfaces.api.app:app --reload        (o `smartcuts api`)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk import capture_exception

from smartcuts.bootstrap import build_storage
from smartcuts.infra.config import Settings, get_settings
from smartcuts.infra.logging import configure_logging, get_logger
from smartcuts.infra.observability import init_sentry
from smartcuts.infra.tls import use_system_trust_store
from smartcuts.interfaces.api.routers import account, dev_storage, jobs, uploads
from smartcuts.interfaces.api.schemas import ErrorResponse
from smartcuts.saas.db import session_factory, session_scope
from smartcuts.saas.dispatch import get_dispatcher
from smartcuts.saas.errors import AppError, user_message
from smartcuts.saas.migrations import upgrade_database
from smartcuts.saas.plans import sync_plans

log = get_logger(__name__)


def create_app(settings: Settings | None = None, *, migrate: bool = True) -> FastAPI:
    settings = settings or get_settings()
    use_system_trust_store()
    configure_logging(settings.log_level, settings.log_json)
    init_sentry(settings, "api")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if migrate and settings.env == "dev":
            upgrade_database(settings)  # en producción las migraciones van en el despliegue
        with session_scope(app.state.sessions) as s:
            sync_plans(s)
        log.info("api.started", env=settings.env, auth=settings.auth.mode, storage=settings.storage.backend)
        yield

    app = FastAPI(
        title="SmartCuts API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env == "dev" else None,
        redoc_url=None,
        responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    )
    app.state.settings = settings
    app.state.sessions = session_factory(settings)
    app.state.storage = build_storage(settings)
    app.state.dispatcher = get_dispatcher(settings)

    # Errores inesperados capturados DENTRO de CORS: si no, la respuesta 500 sale sin cabeceras
    # CORS y el navegador solo muestra un error de CORS en vez del mensaje.
    @app.middleware("http")
    async def catch_unexpected(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            log.exception("api.unhandled", path=request.url.path, error=str(exc))
            capture_exception(exc)
            return JSONResponse(
                {"error": {"code": "internal_error", "message": user_message("internal_error")}}, status_code=500
            )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.web_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500 or exc.detail:
            log.warning("api.app_error", code=exc.code, detail=exc.detail)
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "validation_error", "message": user_message("validation_error")}}, status_code=422
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(account.router)
    app.include_router(uploads.router)
    app.include_router(jobs.router)
    if settings.storage.backend == "local":
        app.include_router(dev_storage.router)
    return app


def __getattr__(name: str):  # `uvicorn smartcuts.interfaces.api.app:app` sin crearla al importar
    if name == "app":
        return create_app()
    raise AttributeError(name)
