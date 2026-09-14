from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event, local
from time import monotonic
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import text

from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
    RepositorioSeguimientoSQL,
)
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ConflictoMensaje
from tests.integracion.datos import estado, recibir
from tests.unitarias.dominio.datos import creacion, propuesta, rechazo


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
def test_primera_insercion_reintenta_inbox_y_completa(
    base: Database, resultado: DatosResultadoCotizacion
) -> None:
    barrera = Barrier(2)
    hilo = local()
    original = RepositorioSeguimientoSQL.guardar
    guardados: list[RepositorioSeguimientoSQL] = []

    def guardar(repositorio: RepositorioSeguimientoSQL, vista: VistaSeguimiento) -> None:
        original(repositorio, vista)
        guardados.append(repositorio)
        if not getattr(hilo, "esperado", False):
            hilo.esperado = True
            barrera.wait(timeout=5)

    with patch.object(RepositorioSeguimientoSQL, "guardar", guardar):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            futuros = [
                ejecutor.submit(recibir, base, fragmento) for fragmento in (creacion(), resultado)
            ]
            for futuro in futuros:
                futuro.result(timeout=10)
    vista, metadatos, entradas = estado(base)
    assert vista is not None and metadatos is not None
    assert vista.creacion == creacion() and vista.resultado == resultado
    assert len(entradas) == 2 and len(guardados) == 3
    assert len(set(guardados)) == 3


@pytest.mark.parametrize("contradictorio", [False, True])
def test_mismo_id_simultaneo(base: Database, contradictorio: bool) -> None:
    barrera = Barrier(2)
    primero = propuesta()
    segundo = replace(primero, importe_menor=1) if contradictorio else primero

    def ejecutar(fragmento: DatosResultadoCotizacion) -> str:
        barrera.wait(timeout=5)
        try:
            recibir(base, fragmento)
            return "ok"
        except ConflictoMensaje:
            return "conflicto"

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        futuros = [ejecutor.submit(ejecutar, fragmento) for fragmento in (primero, segundo)]
        resultados = [futuro.result(timeout=10) for futuro in futuros]
    assert sorted(resultados) == (["conflicto", "ok"] if contradictorio else ["ok", "ok"])
    vista, metadatos, entradas = estado(base)
    assert vista is not None and metadatos is not None and len(entradas) == 1
    assert vista.resultado in (primero, segundo)


@pytest.mark.parametrize("caso", ["peticion", "opuestos", "equivalentes"])
def test_colisiones_empresariales(base: Database, caso: str) -> None:
    original = propuesta()
    if caso == "peticion":
        segundo = replace(
            original,
            identidad=replace(original.identidad, id_trabajo=UUID(int=500)),
            procedencia=replace(original.procedencia, event_id=UUID(int=501)),
        )
    elif caso == "opuestos":
        segundo = rechazo()
    else:
        segundo = replace(
            original, procedencia=replace(original.procedencia, event_id=UUID(int=502))
        )
    guardar_original = RepositorioSeguimientoSQL.guardar
    barrera = Barrier(2)
    hilo = local()

    def guardar(repositorio: RepositorioSeguimientoSQL, vista: VistaSeguimiento) -> None:
        guardar_original(repositorio, vista)
        if not getattr(hilo, "esperado", False):
            hilo.esperado = True
            barrera.wait(timeout=5)

    def ejecutar(fragmento: DatosResultadoCotizacion) -> str:
        try:
            recibir(base, fragmento)
            return "ok"
        except ConflictoFragmentos:
            return "conflicto"

    with patch.object(RepositorioSeguimientoSQL, "guardar", guardar):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            futuros = [ejecutor.submit(ejecutar, fragmento) for fragmento in (original, segundo)]
            resultados = [futuro.result(timeout=10) for futuro in futuros]
    assert sorted(resultados) == (["ok", "ok"] if caso == "equivalentes" else ["conflicto", "ok"])
    with base.engine.connect() as conexion:
        assert conexion.scalar(text("SELECT count(*) FROM seguimiento_trabajos")) == 1
        assert conexion.scalar(text("SELECT count(*) FROM inbox")) == (
            2 if caso == "equivalentes" else 1
        )
        vista_id = conexion.scalar(text("SELECT id_trabajo FROM seguimiento_trabajos"))
        aceptados = list(
            conexion.execute(
                text("SELECT documento->'fragmento'->'identidad'->>'id_trabajo' FROM inbox")
            ).scalars()
        )
        assert all(valor == str(vista_id) for valor in aceptados)


def test_fila_existente_bloquea_segundo_lector_antes_de_combinar(base: Database) -> None:
    recibir(base, creacion())
    bloqueado = Event()
    liberar = Event()
    segundo_iniciado = Event()
    hilo = local()
    procesos: list[int] = []
    original = RepositorioSeguimientoSQL.obtener
    propuesta_original = propuesta()
    equivalente = replace(
        propuesta_original,
        procedencia=replace(propuesta_original.procedencia, event_id=UUID(int=99)),
    )

    def obtener(
        repositorio: RepositorioSeguimientoSQL, id_trabajo: UUID
    ) -> VistaSeguimiento | None:
        if hilo.actor == 2:
            proceso = repositorio.sesion.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(proceso, int)
            procesos.append(proceso)
            segundo_iniciado.set()
        vista = original(repositorio, id_trabajo)
        if hilo.actor == 1:
            bloqueado.set()
            assert liberar.wait(timeout=10)
        return vista

    def ejecutar(actor: int, fragmento: DatosCreacion | DatosResultadoCotizacion) -> None:
        hilo.actor = actor
        recibir(base, fragmento)

    with patch.object(RepositorioSeguimientoSQL, "obtener", obtener):
        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            primero = ejecutor.submit(ejecutar, 1, propuesta_original)
            try:
                assert bloqueado.wait(timeout=5)
                segundo = ejecutor.submit(ejecutar, 2, equivalente)
                assert segundo_iniciado.wait(timeout=5)
                limite = monotonic() + 5
                espera_confirmada = False
                with base.engine.connect() as conexion:
                    while monotonic() < limite:
                        espera_confirmada = bool(
                            conexion.scalar(
                                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                                {"pid": procesos[0]},
                            )
                        )
                        if espera_confirmada:
                            break
                        Event().wait(0.01)
                assert espera_confirmada
            finally:
                liberar.set()
            primero.result(timeout=10)
            segundo.result(timeout=10)
    vista, _, entradas = estado(base)
    assert (
        vista is not None and vista.creacion == creacion() and vista.resultado == propuesta_original
    )
    assert len(entradas) == 3
