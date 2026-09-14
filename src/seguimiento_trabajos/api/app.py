from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request

from seguimiento_trabajos.config.database import Database, create_database
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
        [Database, Settings], AbstractAsyncContextManager[None]
    ] = sin_procesamiento,
) -> FastAPI:
    configuration = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = (
            database_factory(configuration.database_url) if configuration.database_url else None
        )
        application.state.database = database
        try:
            if database is None:
                yield
            else:
                async with processing_factory(database, configuration):
                    yield
        finally:
            application.state.database = None
            if database is not None:
                database.close()

    application = FastAPI(title="Seguimiento de Trabajos", lifespan=lifespan)
    application.state.settings = configuration
    application.state.database = None

    @application.get("/health/live", tags=["health"])
    def liveness(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    return application
