"""Aplicación FastAPI.

    uvicorn clipaso.interfaces.api.app:app --reload        (o `clipaso api`)
"""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk import capture_exception
from sqlalchemy import text

from clipaso.bootstrap import build_storage
from clipaso.infra.config import Settings, get_settings
from clipaso.infra.logging import configure_logging, get_logger
from clipaso.infra.observability import init_sentry
from clipaso.infra.tls import use_system_trust_store
from clipaso.interfaces.api.routers import account, admin, clips, dev_storage, jobs, uploads
from clipaso.interfaces.api.schemas import ErrorResponse
from clipaso.saas.abuse import RateLimiter, client_ip
from clipaso.saas.db import session_factory, session_scope
from clipaso.saas.dispatch import get_dispatcher
from clipaso.saas.errors import AppError, normalize_lang, request_lang, user_message
from clipaso.saas.migrations import upgrade_database
from clipaso.saas.plans import sync_plans

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
        title="Clipaso API",
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
        # Los mensajes para el usuario salen en su idioma (la web envía Accept-Language).
        request_lang.set(normalize_lang(request.headers.get("accept-language")))
        try:
            return await call_next(request)
        except Exception as exc:
            log.exception("api.unhandled", path=request.url.path, error=str(exc))
            capture_exception(exc)
            return JSONResponse(
                {"error": {"code": "internal_error", "message": user_message("internal_error")}}, status_code=500
            )

    limiter = RateLimiter()
    heavy = {("POST", "/uploads"), ("POST", "/jobs"), ("POST", "/jobs/thumbnail"), ("POST", "/signup-check")}

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        # Por sesión (token) y por IP; crear subidas y proyectos, más estricto. Dentro de CORS para que el
        # navegador pueda leer el 429.
        if request.method == "OPTIONS" or request.url.path.startswith("/health"):
            return await call_next(request)
        limits = settings.abuse
        ip = client_ip(request.headers, request.client and request.client.host)
        token = request.headers.get("authorization", "")
        who = hashlib.sha256(token.encode()).hexdigest()[:24] if token else f"ip:{ip}"
        checks = [(f"ip:{ip}", limits.requests_per_minute_ip), (f"u:{who}", limits.requests_per_minute)]
        if (request.method, request.url.path.rstrip("/")) in heavy:
            checks.append((f"heavy:{who}", limits.heavy_per_minute))
        if not all(limiter.allow(key, limit) for key, limit in checks):
            return JSONResponse({"error": {"code": "rate_limited", "message": user_message("rate_limited")}},
                                status_code=429, headers={"Retry-After": "60"})
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api.web_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["ETag"],  # el navegador lo necesita para completar la subida por partes
    )

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500 or exc.detail:
            log.warning("api.app_error", code=exc.code, detail=exc.detail)
        return JSONResponse({"error": {"code": exc.code, "message": exc.message_for()}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {"error": {"code": "validation_error", "message": user_message("validation_error")}}, status_code=422
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["meta"])
    def ready() -> JSONResponse:
        """Para el monitor de disponibilidad: la API responde y llega a la base de datos."""
        try:
            with app.state.sessions() as s:
                s.execute(text("SELECT 1"))
        except Exception as exc:
            log.warning("api.not_ready", error=str(exc))
            return JSONResponse({"status": "db_unavailable"}, status_code=503)
        return JSONResponse({"status": "ok"})

    app.include_router(account.router)
    app.include_router(uploads.router)
    app.include_router(jobs.router)
    app.include_router(clips.router)
    app.include_router(admin.router)
    if settings.storage.backend == "local":
        app.include_router(dev_storage.router)
    return app


def __getattr__(name: str):  # `uvicorn clipaso.interfaces.api.app:app` sin crearla al importar
    if name == "app":
        return create_app()
    raise AttributeError(name)
