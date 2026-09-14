from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from seguimiento_trabajos.api.seguimiento import router
from seguimiento_trabajos.config.database import Database, create_database
from seguimiento_trabajos.config.procesamiento import Procesamiento, procesar_eventos
from seguimiento_trabajos.config.settings import Settings


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@asynccontextmanager
async def sin_procesamiento(database: Database, settings: Settings) -> AsyncIterator[None]:
    yield


def create_app(
    settings: Settings | None = None,
    database_factory: Callable[[str], Database] = create_database,
    processing_factory: Callable[
        [Database, Settings], AbstractAsyncContextManager[Procesamiento | None]
    ] = procesar_eventos,
) -> FastAPI:
    configuration = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = (
            database_factory(configuration.database_url) if configuration.database_url else None
        )
        application.state.database = database
        procesamiento: Procesamiento | None = None
        try:
            if database is None:
                yield
            else:
                async with processing_factory(database, configuration) as procesamiento:
                    application.state.procesamiento = procesamiento
                    yield
        finally:
            application.state.procesamiento = None
            application.state.database = None
            if database is not None and (
                procesamiento is None
                or not any(ciclo.hilo.is_alive() for ciclo in procesamiento.ciclos)
            ):
                database.close()

    application = FastAPI(title="Seguimiento de Trabajos", lifespan=lifespan)
    application.state.settings = configuration
    application.state.database = None
    application.state.procesamiento = None

    @application.get("/health/live", tags=["health"])
    def liveness(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @application.get("/health/ready", tags=["health"])
    def readiness(request: Request) -> JSONResponse:
        procesamiento = request.app.state.procesamiento
        if procesamiento is None:
            return JSONResponse(
                {"status": "unavailable", "motivo": "procesamiento_desactivado"}, status_code=503
            )
        salud = procesamiento.salud()
        return JSONResponse(salud, status_code=200 if salud["status"] == "ok" else 503)

    application.include_router(router)
    return application
