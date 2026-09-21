from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import text

from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.persistencia import crear_uow
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.cancel_tracking import (
    CancelTrackingHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.open_tracking import (
    OpenTrackingHandler,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.outbox import OutboxDispatcher
from seguimiento_trabajos.seedwork.infraestructura.serializacion import Documento
from tests.unitarias.aplicacion.dobles.unidad_trabajo import RelojFijo
from tests.unitarias.aplicacion.test_tracking import cancellation, opening


def test_sql_duplicate_and_durable_reply(base: Database) -> None:
    command = opening()
    OpenTrackingHandler(crear_uow(base), RelojFijo(command.occurred_at))(command)
    OpenTrackingHandler(crear_uow(base), RelojFijo(command.occurred_at))(command)
    with base.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM seguimiento_operativo")) == 1
        assert connection.scalar(text("SELECT count(*) FROM outbox")) == 1
        assert connection.scalar(text("SELECT count(*) FROM inbox")) == 1


def test_concurrent_open_and_cancel_converge(base: Database) -> None:
    command = opening()
    clock = RelojFijo(command.occurred_at)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(OpenTrackingHandler(crear_uow(base), clock), command),
            executor.submit(CancelTrackingHandler(crear_uow(base), clock), cancellation(command)),
        ]
        for future in futures:
            future.result(timeout=10)
    with base.engine.connect() as connection:
        assert connection.scalar(text("SELECT estado FROM seguimiento_operativo")) == "CANCELADO"
        assert connection.scalar(text("SELECT count(*) FROM outbox")) == 2


def test_outbox_retries_identical_payload_after_send_failure(base: Database) -> None:
    command = opening()
    OpenTrackingHandler(crear_uow(base), RelojFijo(command.occurred_at))(command)
    sent: list[Documento] = []

    def fail_after_send(kind: str, payload: Documento) -> None:
        sent.append(payload)
        raise ConnectionError("broker acknowledgement lost")

    with pytest.raises(ConnectionError):
        OutboxDispatcher(base.session_factory, fail_after_send).dispatch_next()

    def send(kind: str, payload: Documento) -> None:
        sent.append(payload)

    dispatcher = OutboxDispatcher(base.session_factory, send)
    assert dispatcher.dispatch_next()
    assert not dispatcher.dispatch_next()
    assert sent[0] == sent[1]


def test_concurrent_first_open_commands_keep_one_tracking(base: Database) -> None:
    command = opening()
    handler = OpenTrackingHandler(crear_uow(base), RelojFijo(command.occurred_at))
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(handler, command),
            executor.submit(handler, replace(command, message_id=uuid4())),
        ]
        for future in futures:
            future.result(timeout=10)
    with base.engine.connect() as connection:
        ids = (
            connection.execute(text("SELECT payload->>'id_seguimiento' FROM outbox"))
            .scalars()
            .all()
        )
        assert len(ids) == 2 and ids[0] == ids[1]


def test_attention_cancellation_before_creation_and_legacy_query(base: Database) -> None:
    from fastapi.testclient import TestClient

    from seguimiento_trabajos.api.app import create_app
    from seguimiento_trabajos.config.settings import Settings
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers import (
        project_work_cancellation,
    )
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.proyectar_creacion import (
        ProyectarCreacionHandler,
    )
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import WorkCancelled
    from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import IdentidadSeguimiento
    from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
        WorkCancellation,
    )
    from tests.unitarias.dominio.datos import creacion

    command = opening()
    event = WorkCancelled(
        message_id=uuid4(),
        identity=command.identity,
        occurred_at=command.occurred_at,
        causation=uuid4(),
        fact=WorkCancellation("COMPENSACION", "Cancelar", command.occurred_at, 2),
    )
    project_work_cancellation.ProjectWorkCancellationHandler(crear_uow(base))(event)
    settings = Settings(database_url=base.engine.url.render_as_string(hide_password=False))
    path = f"/seguimiento/trabajos/{command.identity.work_id}"
    with TestClient(create_app(settings)) as client:
        response = client.get(path + "/atencion")
        assert response.status_code == 200
        assert response.json()["proyeccion"] is None
        assert response.json()["seguimiento_operativo"] is None
        assert response.json()["estado_trabajo"] == "CANCELADO"
        assert client.get(path).status_code == 404
        original = creacion()
        fragment = replace(
            original,
            identidad=IdentidadSeguimiento(
                id_trabajo=command.identity.work_id,
                id_solicitud=command.identity.request_id,
                id_partner=command.identity.partner_id,
                id_peticion=uuid4(),
            ),
            procedencia=replace(original.procedencia, correlacion=command.identity.request_id),
        )
        ProyectarCreacionHandler(crear_uow(base), RelojFijo(command.occurred_at))(fragment)
        assert client.get(path).status_code == 200
        assert client.get(path + "/atencion").json()["estado_trabajo"] == "CANCELADO"
        assert client.get(f"/seguimiento/trabajos/{uuid4()}/atencion").status_code == 404
        assert client.get("/seguimiento/trabajos/not-a-uuid/atencion").status_code == 422


def test_attention_opened_without_projection(base: Database) -> None:
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
        RepositorioLecturaSeguimientoSQL,
    )

    command = opening()
    OpenTrackingHandler(crear_uow(base), RelojFijo(command.occurred_at))(command)
    view = RepositorioLecturaSeguimientoSQL(base.session_factory).get_attention(
        command.identity.work_id
    )
    assert view is not None and view.proyeccion is None
    assert view.seguimiento_operativo is not None
    assert view.seguimiento_operativo.estado == "ABIERTO"


def test_two_dispatchers_do_not_publish_same_row_concurrently(base: Database) -> None:
    from threading import Barrier, Lock

    commands = [opening(), opening()]
    for command in commands:
        OpenTrackingHandler(crear_uow(base), RelojFijo(command.occurred_at))(command)
    barrier = Barrier(2)
    lock = Lock()
    sent: list[str] = []

    def send(kind: str, payload: Documento) -> None:
        barrier.wait(timeout=5)
        with lock:
            sent.append(str(payload["event_id"]))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(OutboxDispatcher(base.session_factory, send).dispatch_next)
            for _ in range(2)
        ]
        assert all(future.result(timeout=10) for future in futures)
    assert len(sent) == len(set(sent)) == 2


def test_migration_preserves_legacy_data_and_matches_metadata(base: Database) -> None:
    from pathlib import Path

    from alembic import command as migration
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext

    from seguimiento_trabajos.config.persistencia import metadata
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.proyectar_creacion import (
        ProyectarCreacionHandler,
    )
    from tests.unitarias.dominio.datos import creacion

    sample = creacion()
    ProyectarCreacionHandler(crear_uow(base), RelojFijo(sample.creado_en))(sample)
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    with base.engine.begin() as connection:
        config.attributes["connection"] = connection
        migration.downgrade(config, "0001")
        assert connection.scalar(text("SELECT count(*) FROM seguimiento_trabajos")) == 1
        migration.upgrade(config, "head")
        assert connection.scalar(text("SELECT count(*) FROM seguimiento_trabajos")) == 1
        assert compare_metadata(MigrationContext.configure(connection), metadata) == []
