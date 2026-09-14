import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Any
from uuid import uuid4

import pulsar
import pytest
from fastapi.testclient import TestClient
from pulsar.schema import AvroSchema

from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.config.bootstrap import componer_consumidores
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.rutas import fuentes
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.eventos import esquemas
from tests.integracion.datos import estado

CONTRATOS = Path(__file__).resolve().parents[2] / "docs/contratos"


def preparar(settings: Settings) -> None:
    environment = {
        **os.environ,
        "SEGUIMIENTO_PROCESSING_ENABLED": "false",
        "SEGUIMIENTO_PULSAR_URL": settings.pulsar_url,
        "SEGUIMIENTO_TOPICO_CREACION": settings.topico_creacion,
        "SEGUIMIENTO_TOPICO_REGISTRADA": settings.topico_registrada,
        "SEGUIMIENTO_TOPICO_RECHAZADA": settings.topico_rechazada,
    }
    subprocess.run(
        [sys.executable, "scripts/preparar_pulsar.py"],
        env=environment,
        check=True,
        capture_output=True,
        timeout=20,
    )


def esperar(condicion: Callable[[], bool], timeout: float = 12) -> None:
    limite = monotonic() + timeout
    while not condicion():
        if monotonic() >= limite:
            pytest.fail("No se observo la condicion dentro del plazo")
        Event().wait(0.02)


@pytest.fixture
def configuracion(base: Database) -> Settings:
    prefijo = f"persistent://public/default/seguimiento-test-{uuid4().hex}-"
    return Settings(
        processing_enabled=True,
        database_url=base.engine.url.render_as_string(hide_password=False),
        pulsar_url=os.getenv("SEGUIMIENTO_TEST_PULSAR_URL", "pulsar://127.0.0.1:6650"),
        topico_creacion=prefijo + "creacion",
        topico_registrada=prefijo + "registrada",
        topico_rechazada=prefijo + "rechazada",
        recepcion_ms=100,
        pausa_reintento=0.05,
    )


@pytest.fixture
def publicador(configuracion: Settings) -> Iterator[Callable[..., Any]]:
    preparar(configuracion)
    cliente = pulsar.Client(
        configuracion.pulsar_url, operation_timeout_seconds=2, connection_timeout_ms=1000
    )
    productores = {
        fuente.nombre: cliente.create_producer(
            fuente.topico, schema=AvroSchema(esquemas()[fuente.nombre]), batching_enabled=False
        )
        for fuente in fuentes(configuracion)
    }

    def publicar(nombre: str, **cambios: Any) -> Any:
        documento = json.loads((CONTRATOS / f"{nombre}-v1.ejemplo.json").read_text())
        documento.update(cambios)
        return productores[nombre].send(
            esquemas()[nombre](**documento), partition_key=documento["id_trabajo"]
        )

    try:
        yield publicar
    finally:
        cliente.close()


@pytest.mark.parametrize("resultado", ["cotizacion-registrada", "cotizacion-rechazada"])
@pytest.mark.parametrize("resultado_primero", [False, True])
def test_consumo_autonomo_ambos_ordenes_y_reinicio(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    resultado: str,
    resultado_primero: bool,
) -> None:
    app = create_app(configuracion)
    primero, segundo = (
        (resultado, "trabajo-creado") if resultado_primero else ("trabajo-creado", resultado)
    )
    publicador(primero)
    preparar(configuracion)
    with TestClient(app) as client:
        esperar(lambda: len(estado(base)[2]) == 1)
        vista, _, _ = estado(base)
        assert vista is not None and vista.creacion_recibida == (not resultado_primero)
        publicador(segundo)
        esperar(lambda: len(estado(base)[2]) == 2)
        antes = estado(base)
        assert antes[0] is not None and antes[0].creacion_recibida
        esperar(lambda: client.get("/health/ready").status_code == 200)
        assert client.get("/health/live").status_code == 200
    inicio = monotonic()
    with TestClient(app) as client:
        publicador(primero)
        publicador(resultado, event_id=str(uuid4()))
        esperar(lambda: len(estado(base)[2]) == 3)
        assert estado(base)[:2] == antes[:2]
        esperar(lambda: client.get("/health/ready").status_code == 200)
    assert monotonic() - inicio < 10


def test_conflicto_pausa_fuente_sin_ack_y_otras_siguen(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
) -> None:
    app = create_app(configuracion)
    with TestClient(app) as client:
        publicador("cotizacion-registrada")
        esperar(lambda: len(estado(base)[2]) == 1)
        anterior = estado(base)
        publicador("cotizacion-registrada", importe_menor=1)
        esperar(lambda: app.state.procesamiento.ciclos[1].estado()["estado"] == "pausado")
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200
        assert estado(base) == anterior
        diagnostico = app.state.procesamiento.ciclos[1].estado()["diagnostico"]
        assert diagnostico["event_id"] and diagnostico["message_id"]
        publicador("trabajo-creado")
        esperar(lambda: len(estado(base)[2]) == 2)
    consumidores = componer_consumidores(base, configuracion)
    try:
        from seguimiento_trabajos.seedwork.infraestructura.ciclos import FalloPaso

        with pytest.raises(FalloPaso):
            consumidores[1].procesar_siguiente()
    finally:
        for consumidor in consumidores:
            consumidor.cerrar()


def test_dos_instancias_comparten_suscripcion_y_conservan_fragmentos(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
) -> None:
    app1, app2 = create_app(configuracion), create_app(configuracion)
    with TestClient(app1), TestClient(app2):
        publicador("trabajo-creado")
        publicador("cotizacion-registrada")
        for _ in range(4):
            publicador("cotizacion-registrada")
        publicador("cotizacion-registrada", event_id=str(uuid4()))
        esperar(lambda: len(estado(base)[2]) == 3)
        vista, _, entradas = estado(base)
        assert vista is not None and vista.creacion is not None and vista.resultado is not None
        assert {fila[0] for fila in entradas} == {"seguimiento.proyeccion"}


def test_fanout_suscripcion_independiente(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
) -> None:
    cliente = pulsar.Client(configuracion.pulsar_url)
    otro = cliente.subscribe(
        configuracion.topico_registrada,
        "doble-orquestacion",
        schema=AvroSchema(esquemas()["cotizacion-registrada"]),
        initial_position=pulsar.InitialPosition.Earliest,
    )
    try:
        with TestClient(create_app(configuracion)):
            identificador = publicador("cotizacion-registrada")
            mensaje = otro.receive(timeout_millis=5000)
            assert mensaje.message_id() == identificador
            otro.acknowledge(mensaje)
            esperar(lambda: len(estado(base)[2]) == 1)
    finally:
        cliente.close()


@pytest.mark.parametrize(
    "resultado,indice", [("cotizacion-registrada", 1), ("cotizacion-rechazada", 2)]
)
@pytest.mark.parametrize("punto", ["antes_commit", "despues_commit"])
def test_corte_de_proceso_y_reentrega_real(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    resultado: str,
    indice: int,
    punto: str,
) -> None:
    from dataclasses import asdict

    publicador(resultado)
    programa = """
import json, os, signal, sys
from seguimiento_trabajos.config.database import create_database
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.config.bootstrap import componer_consumidores
from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL
settings = Settings(**json.loads(os.environ['SEGUIMIENTO_TEST_CONFIG']))
base = create_database(settings.database_url)
consumidor = componer_consumidores(base, settings)[int(sys.argv[1])]
original = consumidor.procesar
punto = sys.argv[2]
def matar(*args):
    os.kill(os.getpid(), signal.SIGKILL)
if punto == 'antes_commit':
    UnidadTrabajoSQL.confirmar = matar
def procesar(mensaje):
    print('MESSAGE_ID=' + str(mensaje.message_id()), flush=True)
    original(mensaje)
    if punto == 'despues_commit':
        matar()
consumidor.procesar = procesar
try:
    for intento in range(50):
        if consumidor.procesar_siguiente():
            print('ACK_OK', flush=True)
            break
    else:
        raise RuntimeError('No llego el mensaje')
finally:
    consumidor.cerrar()
    base.close()
"""
    environment = {**os.environ, "SEGUIMIENTO_TEST_CONFIG": json.dumps(asdict(configuracion))}
    primero = subprocess.run(
        [sys.executable, "-c", programa, str(indice), punto],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert primero.returncode == -9, primero.stderr
    assert len(estado(base)[2]) == int(punto == "despues_commit")
    segundo = subprocess.run(
        [sys.executable, "-c", programa, str(indice), "recuperacion"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert segundo.returncode == 0, segundo.stderr
    assert "ACK_OK" in segundo.stdout

    def identificadores(salida: str) -> list[str]:
        return [linea for linea in salida.splitlines() if linea.startswith("MESSAGE_ID=")]

    assert identificadores(primero.stdout) == identificadores(segundo.stdout)
    assert len(identificadores(segundo.stdout)) == 1
    assert len(estado(base)[2]) == 1
    print(f"{resultado} {punto}: mismo MessageId reentregado, un efecto SQL")


def test_orden_adverso_con_barrera_antes_del_handler(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seguimiento_trabajos.config import procesamiento

    recibido, liberar = Event(), Event()
    original = componer_consumidores

    def componer(database: Database, settings: Settings) -> Any:
        consumidores = original(database, settings)
        procesar = consumidores[0].procesar

        def demorar(mensaje: Any) -> None:
            recibido.set()
            assert liberar.wait(5)
            procesar(mensaje)

        consumidores[0].procesar = demorar
        return consumidores

    monkeypatch.setattr(procesamiento, "componer_consumidores", componer)
    try:
        with TestClient(create_app(configuracion)):
            publicador("trabajo-creado")
            assert recibido.wait(3)
            publicador("cotizacion-registrada")
            esperar(lambda: len(estado(base)[2]) == 1)
            parcial = estado(base)[0]
            assert parcial is not None and not parcial.creacion_recibida
            liberar.set()
            esperar(lambda: len(estado(base)[2]) == 2)
            completa = estado(base)[0]
            assert completa is not None and completa.resultado == parcial.resultado
    finally:
        liberar.set()


def test_limites_sql_y_rollback_tras_statement_timeout(base: Database) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    with base.engine.connect() as conexion:
        assert conexion.scalar(text("SHOW statement_timeout")) == "1s"
        assert conexion.scalar(text("SHOW lock_timeout")) == "500ms"
        assert conexion.scalar(text("SHOW transaction_timeout")) == "2s"
        with pytest.raises(OperationalError):
            conexion.execute(text("SELECT pg_sleep(2)"))
        conexion.rollback()
        assert conexion.scalar(text("SELECT 1")) == 1


def test_transitorio_sql_rollback_reentrega_y_recuperacion(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import OperationalError

    from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import (
        UnidadTrabajoSQL,
    )

    original = UnidadTrabajoSQL.confirmar
    fallo = Event()

    def confirmar(unidad: UnidadTrabajoSQL) -> None:
        if not fallo.is_set():
            unidad.sesion.flush()
            fallo.set()
            raise OperationalError("fallo controlado", {}, ConnectionError("temporal"))
        original(unidad)

    monkeypatch.setattr(UnidadTrabajoSQL, "confirmar", confirmar)
    app = create_app(replace(configuracion, pausa_reintento=0.5))
    with TestClient(app) as client:
        publicador("trabajo-creado")
        assert fallo.wait(3)
        esperar(lambda: app.state.procesamiento.ciclos[0].estado()["estado"] == "recuperando")
        assert estado(base) == (None, None, [])
        assert client.get("/health/ready").status_code == 503
        esperar(lambda: len(estado(base)[2]) == 1)
        esperar(lambda: client.get("/health/ready").status_code == 200)


def test_reconexion_real_de_un_cliente_sin_detener_broker_compartido(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seguimiento_trabajos.config import procesamiento

    original = componer_consumidores
    desconectado = Event()

    def componer(database: Database, settings: Settings) -> Any:
        consumidores = original(database, settings)
        consumidor = consumidores[0]
        paso = consumidor.procesar_siguiente

        def desconectar() -> bool:
            if not desconectado.is_set():
                consumidor.abrir()
                consumidor._cliente.close()
                desconectado.set()
            return paso()

        monkeypatch.setattr(consumidor, "procesar_siguiente", desconectar)
        return consumidores

    monkeypatch.setattr(procesamiento, "componer_consumidores", componer)
    app = create_app(replace(configuracion, pausa_reintento=0.5))
    with TestClient(app) as client:
        assert desconectado.wait(3)
        esperar(lambda: app.state.procesamiento.ciclos[0].estado()["estado"] == "recuperando")
        publicador("trabajo-creado")
        esperar(lambda: len(estado(base)[2]) == 1)
        esperar(lambda: client.get("/health/ready").status_code == 200)


def test_parada_durante_sql_acotada_y_sin_ack(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import text

    from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import (
        UnidadTrabajoSQL,
    )

    dentro = Event()
    original = UnidadTrabajoSQL.confirmar

    def confirmar(unidad: UnidadTrabajoSQL) -> None:
        dentro.set()
        unidad.sesion.execute(text("SELECT pg_sleep(3)"))
        original(unidad)

    monkeypatch.setattr(UnidadTrabajoSQL, "confirmar", confirmar)
    inicio = monotonic()
    with TestClient(create_app(configuracion)):
        publicador("trabajo-creado")
        assert dentro.wait(3)
        inicio = monotonic()
    assert monotonic() - inicio < 9
    assert estado(base) == (None, None, [])
    monkeypatch.setattr(UnidadTrabajoSQL, "confirmar", original)
    with TestClient(create_app(configuracion)):
        esperar(lambda: len(estado(base)[2]) == 1)


@pytest.mark.parametrize("resultado", ["cotizacion-registrada", "cotizacion-rechazada"])
def test_http_real_con_consumo_y_cierre_limpio(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    resultado: str,
) -> None:
    import signal
    import socket
    import urllib.error
    import urllib.request

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        puerto = probe.getsockname()[1]
    environment = {
        **os.environ,
        "SEGUIMIENTO_PROCESSING_ENABLED": "true",
        "SEGUIMIENTO_DATABASE_URL": str(configuracion.database_url),
        "SEGUIMIENTO_PULSAR_URL": configuracion.pulsar_url,
        "SEGUIMIENTO_TOPICO_CREACION": configuracion.topico_creacion,
        "SEGUIMIENTO_TOPICO_REGISTRADA": configuracion.topico_registrada,
        "SEGUIMIENTO_TOPICO_RECHAZADA": configuracion.topico_rechazada,
    }
    proceso = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "seguimiento_trabajos.api.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(puerto),
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def listo() -> bool:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{puerto}/health/ready", timeout=2
            ) as respuesta:
                return bool(respuesta.status == 200)
        except (OSError, urllib.error.HTTPError):
            return False

    try:
        esperar(listo)
        from tests.unitarias.dominio.datos import identidad

        url = f"http://127.0.0.1:{puerto}/seguimiento/trabajos/{identidad().id_trabajo}"

        def consultar() -> dict[str, Any]:
            with urllib.request.urlopen(url, timeout=2) as response:
                documento: dict[str, Any] = json.load(response)
                return documento

        publicador(resultado)
        esperar(lambda: len(estado(base)[2]) == 1)
        parcial = consultar()
        assert parcial["creacion_recibida"] is False
        assert parcial["referencia_externa"] is None
        assert parcial["estado"] == (
            "COTIZACION_REGISTRADA"
            if resultado == "cotizacion-registrada"
            else "COTIZACION_RECHAZADA"
        )
        publicador("trabajo-creado")
        esperar(lambda: len(estado(base)[2]) == 2)
        completa = consultar()
        assert completa["creacion_recibida"] is True
        assert completa["referencia_externa"] is not None
        for campo in ("estado", "id_cotizacion", "importe_menor", "motivo"):
            assert completa[campo] == parcial[campo]
        antes = estado(base)
        assert consultar() == completa
        assert estado(base) == antes
        assert listo()
    finally:
        inicio = monotonic()
        proceso.send_signal(signal.SIGTERM)
        try:
            salida, _ = proceso.communicate(timeout=9)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.communicate()
            raise
        assert monotonic() - inicio < 9
    assert "Application shutdown complete." in salida


def test_avro_corrupto_pausa_sin_inbox(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cliente = pulsar.Client(configuracion.pulsar_url)
    schema = AvroSchema(esquemas()["cotizacion-rechazada"])
    monkeypatch.setattr(schema, "encode", lambda _: b"")
    productor = cliente.create_producer(
        configuracion.topico_rechazada, schema=schema, batching_enabled=False
    )
    app = create_app(configuracion)
    try:
        with TestClient(app) as client:
            productor.send(None, partition_key="00000000-0000-0000-0000-000000000001")
            esperar(lambda: app.state.procesamiento.ciclos[2].estado()["estado"] == "pausado")
            assert estado(base) == (None, None, [])
            assert client.get("/health/ready").status_code == 503
            assert app.state.procesamiento.ciclos[2].estado()["diagnostico"]["message_id"]
    finally:
        cliente.close()


def test_preparar_no_reinicia_cursor_confirmado(
    base: Database,
    configuracion: Settings,
    publicador: Callable[..., Any],
) -> None:
    consumidores = componer_consumidores(base, configuracion)
    consumidor = consumidores[0]
    try:
        primero = publicador("trabajo-creado")
        assert consumidor.procesar_siguiente()
    finally:
        consumidor.cerrar()
    preparar(configuracion)
    segundo = publicador("trabajo-creado", event_id=str(uuid4()))
    observados: list[Any] = []
    consumidores = componer_consumidores(base, configuracion)
    consumidor = consumidores[0]
    procesar = consumidor.procesar

    def registrar(mensaje: Any) -> None:
        observados.append(mensaje.message_id())
        procesar(mensaje)

    consumidor.procesar = registrar
    try:
        assert consumidor.procesar_siguiente()
        assert observados == [segundo]
        assert primero != segundo
        assert len(estado(base)[2]) == 2
    finally:
        consumidor.cerrar()
