import os
from dataclasses import replace
from uuid import uuid4

import pulsar
import pytest
from fastapi.testclient import TestClient
from pulsar.schema import AvroSchema

from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.rutas import reply_topics, saga_sources
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import WorkCancelled
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import WorkCancellation
from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.saga import saga_schemas
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import (
    saga_document,
)
from tests.integracion.test_pulsar import esperar
from tests.unitarias.aplicacion.test_tracking import cancellation, opening


@pytest.mark.parametrize(
    "scenario", ["success", "controlled_failure", "cancel_first", "work_cancel_first"]
)
def test_participant_over_real_pulsar(base: Database, scenario: str) -> None:
    command = opening()
    prefix = f"persistent://public/default/seguimiento-e5-{uuid4().hex}-"
    settings = Settings(
        database_url=base.engine.url.render_as_string(hide_password=False),
        processing_enabled=True,
        pulsar_url=os.getenv("SEGUIMIENTO_TEST_PULSAR_URL", "pulsar://127.0.0.1:6650"),
        topico_creacion=prefix + "creation",
        topico_registrada=prefix + "quote",
        topico_rechazada=prefix + "rejection",
        topico_apertura=prefix + "open",
        topico_cancelacion=prefix + "cancel",
        topico_trabajo_cancelado=prefix + "work-cancel",
        topico_abierto=prefix + "opened",
        topico_apertura_fallida=prefix + "failed",
        topico_cancelado=prefix + "cancelled",
        pausa_reintento=0.02,
        recepcion_ms=50,
        fail_opening_work_id=command.identity.work_id if scenario == "controlled_failure" else None,
    )
    schemas = saga_schemas()
    broker = pulsar.Client(
        settings.pulsar_url, operation_timeout_seconds=3, connection_timeout_ms=1000
    )
    try:
        replies = {
            kind: broker.subscribe(
                topic,
                "test-replies",
                schema=AvroSchema(schemas[kind]),
                initial_position=pulsar.InitialPosition.Earliest,
            )
            for kind, topic in reply_topics(settings).items()
        }
        producers = {
            source.tipo: broker.create_producer(
                source.topico, schema=AvroSchema(schemas[source.tipo]), batching_enabled=False
            )
            for source in saga_sources(settings)
        }
        path = f"/seguimiento/trabajos/{command.identity.work_id}/atencion"
        with TestClient(create_app(settings)) as client:
            esperar(lambda: client.get("/health/ready").status_code == 200)
            if scenario == "cancel_first":
                cancel = cancellation(command)
                producers[cancel.contract].send(
                    schemas[cancel.contract](**saga_document(cancel)),
                    partition_key=str(command.identity.work_id),
                )
                received = replies["SeguimientoTrabajoCancelado.v1"].receive(timeout_millis=8000)
                assert received.value().id_seguimiento is None
                replies["SeguimientoTrabajoCancelado.v1"].acknowledge(received)
            elif scenario == "work_cancel_first":
                event = WorkCancelled(
                    message_id=uuid4(),
                    identity=command.identity,
                    occurred_at=command.occurred_at,
                    causation=uuid4(),
                    fact=WorkCancellation("COMPENSACION", "Cancelar", command.occurred_at, 2),
                )
                producers[event.contract].send(
                    schemas[event.contract](**saga_document(event)),
                    partition_key=str(command.identity.work_id),
                )
                esperar(lambda: client.get(path).status_code == 200)
                assert client.get(path).json()["estado_trabajo"] == "CANCELADO"
            producers[command.contract].send(
                schemas[command.contract](**saga_document(command)),
                partition_key=str(command.identity.work_id),
            )
            result_type = (
                "SeguimientoTrabajoAbierto.v1"
                if scenario == "success"
                else "AperturaSeguimientoFallida.v1"
            )
            received = replies[result_type].receive(timeout_millis=8000)
            result = received.value()
            assert result.causacion == str(command.message_id)
            assert result.correlacion == str(command.identity.request_id)
            assert result.id_saga == str(command.identity.saga_id)
            replies[result_type].acknowledge(received)
            if scenario == "success":
                assert client.get(path).json()["seguimiento_operativo"]["estado"] == "ABIERTO"
                cancel = cancellation(command)
                producers[cancel.contract].send(
                    schemas[cancel.contract](**saga_document(cancel)),
                    partition_key=str(command.identity.work_id),
                )
                cancelled = replies["SeguimientoTrabajoCancelado.v1"].receive(timeout_millis=8000)
                assert cancelled.value().id_seguimiento == result.id_seguimiento
                replies["SeguimientoTrabajoCancelado.v1"].acknowledge(cancelled)
                assert client.get(path).json()["seguimiento_operativo"]["estado"] == "CANCELADO"
            elif scenario == "controlled_failure":
                assert result.codigo_motivo == "FALLO_CONTROLADO_APERTURA"
                assert client.get(path).status_code == 404
        # Re-delivery after process lifecycle restart keeps the original outbox identity.
        from sqlalchemy import text

        with base.engine.connect() as connection:
            before = (
                connection.execute(text("SELECT event_id FROM outbox ORDER BY event_id"))
                .scalars()
                .all()
            )
        producers[command.contract].send(
            schemas[command.contract](**saga_document(command)),
            partition_key=str(command.identity.work_id),
        )
        with TestClient(create_app(replace(settings, fail_opening_work_id=None))) as client:
            esperar(lambda: client.get("/health/ready").status_code == 200)
        with base.engine.connect() as connection:
            after = (
                connection.execute(text("SELECT event_id FROM outbox ORDER BY event_id"))
                .scalars()
                .all()
            )
            assert before == after
    finally:
        broker.close()


@pytest.mark.parametrize("point", ["before_commit", "after_commit"])
def test_real_command_redelivery_after_process_crash(base: Database, point: str) -> None:
    import json
    import subprocess
    import sys
    from dataclasses import asdict

    from sqlalchemy import text

    command = opening()
    topic = f"persistent://public/default/e5-crash-{uuid4().hex}"
    settings = Settings(
        database_url=base.engine.url.render_as_string(hide_password=False),
        pulsar_url=os.getenv("SEGUIMIENTO_TEST_PULSAR_URL", "pulsar://127.0.0.1:6650"),
        topico_apertura=topic,
        recepcion_ms=100,
    )
    broker = pulsar.Client(settings.pulsar_url, operation_timeout_seconds=3)
    schema = AvroSchema(saga_schemas()[command.contract])
    try:
        subscription = broker.subscribe(
            topic,
            "seguimiento-apertura-v1",
            schema=schema,
            initial_position=pulsar.InitialPosition.Earliest,
            consumer_type=pulsar.ConsumerType.Shared,
        )
        subscription.close()
        producer = broker.create_producer(topic, schema=schema)
        producer.send(
            saga_schemas()[command.contract](**saga_document(command)),
            partition_key=str(command.identity.work_id),
        )
        program = """
import json, os, signal, sys
from seguimiento_trabajos.config.database import create_database
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.config.bootstrap import componer_consumidores
from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL
settings = Settings(**json.loads(os.environ['SEGUIMIENTO_TEST_CONFIG']))
base = create_database(settings.database_url)
consumer = componer_consumidores(base, settings)[3]
original = consumer.procesar
def crash(*args):
    os.kill(os.getpid(), signal.SIGKILL)
if sys.argv[1] == 'before_commit':
    UnidadTrabajoSQL.confirmar = crash
def process(message):
    print('MESSAGE_ID=' + str(message.message_id()), flush=True)
    original(message)
    if sys.argv[1] == 'after_commit':
        crash()
consumer.procesar = process
try:
    for attempt in range(80):
        if consumer.procesar_siguiente():
            print('ACK_OK', flush=True)
            break
    else:
        raise RuntimeError('Command not received')
finally:
    consumer.cerrar()
    base.close()
"""
        environment = {**os.environ, "SEGUIMIENTO_TEST_CONFIG": json.dumps(asdict(settings))}
        first = subprocess.run(
            [sys.executable, "-c", program, point],
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert first.returncode == -9, first.stderr
        with base.engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM outbox")) == int(
                point == "after_commit"
            )
            original_ids = connection.execute(text("SELECT event_id FROM outbox")).scalars().all()
        second = subprocess.run(
            [sys.executable, "-c", program, "recover"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert second.returncode == 0 and "ACK_OK" in second.stdout, second.stderr
        assert [line for line in first.stdout.splitlines() if line.startswith("MESSAGE_ID=")] == [
            line for line in second.stdout.splitlines() if line.startswith("MESSAGE_ID=")
        ]
        with base.engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM seguimiento_operativo")) == 1
            ids = connection.execute(text("SELECT event_id FROM outbox")).scalars().all()
            assert len(ids) == 1
            if original_ids:
                assert ids == original_ids
    finally:
        broker.close()
