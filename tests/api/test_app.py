from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from seguimiento_trabajos.api.app import create_app, get_settings
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.settings import Settings


@asynccontextmanager
async def sin_procesamiento(base: Database, settings: Settings) -> AsyncIterator[None]:
    yield


def test_liveness_without_infrastructure() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "seguimiento-trabajos"}


def test_overrides_are_scoped_to_each_application() -> None:
    first_app = create_app(Settings(service_name="first"))
    second_app = create_app(Settings(service_name="second"))
    first_app.dependency_overrides[get_settings] = lambda: Settings(service_name="overridden")
    try:
        with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
            assert first_client.get("/health/live").json()["service"] == "overridden"
            assert second_client.get("/health/live").json()["service"] == "second"
    finally:
        first_app.dependency_overrides.clear()
    assert second_app.dependency_overrides == {}
    with TestClient(first_app) as client:
        assert client.get("/health/live").json()["service"] == "first"


@pytest.mark.parametrize("raise_error", [False, True])
def test_owned_database_is_closed_even_on_error(raise_error: bool) -> None:
    database = Mock(spec=Database)
    factory = Mock(return_value=database)
    application = create_app(
        Settings(database_url="postgresql+psycopg://test"), factory, sin_procesamiento
    )

    def exercise_lifespan() -> None:
        with TestClient(application) as client:
            assert client.get("/health/live").status_code == 200
            database.close.assert_not_called()
            if raise_error:
                raise RuntimeError("operation failed")

    if raise_error:
        with pytest.raises(RuntimeError, match="operation failed"):
            exercise_lifespan()
    else:
        exercise_lifespan()
    factory.assert_called_once_with("postgresql+psycopg://test")
    database.close.assert_called_once_with()
    assert application.state.database is None


def test_database_resources_are_not_shared_between_applications() -> None:
    first_database = Mock(spec=Database)
    second_database = Mock(spec=Database)
    factory = Mock(side_effect=[first_database, second_database])
    settings = Settings(database_url="postgresql+psycopg://test")
    first_app = create_app(settings, factory, sin_procesamiento)
    second_app = create_app(settings, factory, sin_procesamiento)
    with TestClient(first_app), TestClient(second_app):
        assert first_app.state.database is first_database
        assert second_app.state.database is second_database
    first_database.close.assert_called_once_with()
    second_database.close.assert_called_once_with()


def test_no_database_factory_is_called_without_configuration() -> None:
    factory = Mock(side_effect=AssertionError("database not configured"))
    with TestClient(create_app(Settings(), factory)) as client:
        assert client.get("/health/live").status_code == 200
    factory.assert_not_called()


@pytest.mark.parametrize("failure_stage", ["none", "startup", "request", "shutdown"])
def test_processing_lifecycle_and_database_cleanup(failure_stage: str) -> None:
    stages: list[str] = []
    database = Mock(spec=Database)
    database.close.side_effect = lambda: stages.append("database_closed")
    settings = Settings(database_url="postgresql+psycopg://test")

    @asynccontextmanager
    async def processing(base: Database, configuration: Settings) -> AsyncIterator[None]:
        assert base is database
        assert configuration is settings
        stages.append("processing_started")
        try:
            if failure_stage == "startup":
                raise RuntimeError("startup")
            yield
            if failure_stage == "shutdown":
                raise RuntimeError("shutdown")
        finally:
            stages.append("processing_closed")

    application = create_app(settings, Mock(return_value=database), processing)
    assert stages == []

    def exercise() -> None:
        with TestClient(application) as client:
            assert client.get("/health/live").status_code == 200
            assert stages == ["processing_started"]
            if failure_stage == "request":
                raise RuntimeError("request")

    if failure_stage == "none":
        exercise()
    else:
        with pytest.raises(RuntimeError, match=failure_stage):
            exercise()
    assert stages == ["processing_started", "processing_closed", "database_closed"]
    assert application.state.database is None


def test_lifespan_can_restart_with_fresh_resources() -> None:
    first_database = Mock(spec=Database)
    second_database = Mock(spec=Database)
    factory = Mock(side_effect=[first_database, second_database])
    application = create_app(
        Settings(database_url="postgresql+psycopg://test"), factory, sin_procesamiento
    )
    for expected_database in (first_database, second_database):
        with TestClient(application):
            assert application.state.database is expected_database
        expected_database.close.assert_called_once_with()
        assert application.state.database is None
