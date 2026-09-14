from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.persistencia import crear_uow, metadata
from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import DatosResultadoCotizacion
from seguimiento_trabajos.modulos.seguimiento.infraestructura.unidad_trabajo import (
    UnidadTrabajoSeguimientoSQL,
)
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ConflictoMensaje
from tests.integracion.datos import INSTANTE, estado, recibir
from tests.unitarias.dominio.datos import creacion, propuesta, rechazo


def test_migracion_y_orm_coinciden(base: Database) -> None:
    with base.engine.connect() as conexion:
        assert compare_metadata(MigrationContext.configure(conexion), metadata) == []
        assert conexion.scalar(text("SHOW transaction_isolation")) == "read committed"
    with pytest.raises(IntegrityError):
        with base.engine.begin() as conexion:
            conexion.execute(
                text("""INSERT INTO seguimiento_trabajos
                (id_trabajo,id_peticion,id_solicitud,id_partner,estado,creacion_recibida,
                 primera_recepcion_en,proyectada_en)
                VALUES (:trabajo,:peticion,:solicitud,:partner,
                    'PENDIENTE_COTIZACION',false,now(),now())"""),
                dict(
                    trabajo=UUID(int=1),
                    peticion=UUID(int=2),
                    solicitud=UUID(int=3),
                    partner=UUID(int=4),
                ),
            )


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
@pytest.mark.parametrize("inverso", [False, True])
def test_ordenes_fragmentos_columnas_y_fechas(
    base: Database, resultado: DatosResultadoCotizacion, inverso: bool
) -> None:
    primero, segundo = (resultado, creacion()) if inverso else (creacion(), resultado)
    recibir(base, primero)
    parcial, fechas, entradas = estado(base)
    assert parcial is not None and fechas is not None and len(entradas) == 1
    assert (parcial.resultado if inverso else parcial.creacion) == primero
    recibir(base, segundo, INSTANTE + timedelta(minutes=1))
    vista, fechas, entradas = estado(base)
    assert vista is not None and fechas is not None
    assert vista.creacion == creacion() and vista.resultado == resultado
    assert fechas.primera_recepcion_en == INSTANTE
    assert fechas.proyectada_en == INSTANTE + timedelta(minutes=1)
    assert len(entradas) == 2
    with base.engine.connect() as conexion:
        fila = conexion.execute(text("SELECT * FROM seguimiento_trabajos")).mappings().one()
        assert fila["estado"] == vista.estado and fila["creacion_recibida"]
        assert fila["categoria"] == vista.categoria and fila["tipo_red"] == vista.tipo_red
        assert (
            fila["referencia_externa"] == vista.referencia_externa
            and fila["creado_en"] == vista.creado_en
        )
    anterior = estado(base)
    recibir(base, primero, INSTANTE + timedelta(days=2))
    recibir(base, segundo, INSTANTE + timedelta(days=2))
    assert estado(base) == anterior


@pytest.mark.parametrize("campo", ["importe", "instante", "revision", "causacion"])
def test_inbox_equivalente_y_alteracion(base: Database, campo: str) -> None:
    original = propuesta()
    equivalente = replace(
        original, procedencia=replace(original.procedencia, event_id=UUID(int=99))
    )
    recibir(base, original)
    anterior = estado(base)
    recibir(base, equivalente, INSTANTE + timedelta(days=1))
    actual = estado(base)
    assert actual[:2] == anterior[:2] and len(actual[2]) == 2
    if campo == "importe":
        alterado = replace(equivalente, importe_menor=10)
    else:
        valores: dict[str, Any] = {
            "instante": INSTANTE,
            "version_contrato": 2,
            "causacion": UUID(int=500),
        }
        nombre = "version_contrato" if campo == "revision" else campo
        alterado = replace(
            equivalente, procedencia=replace(equivalente.procedencia, **{nombre: valores[nombre]})
        )
    with pytest.raises(ConflictoMensaje):
        recibir(base, alterado)
    assert estado(base) == actual


@pytest.mark.parametrize("otro_tipo", [False, True])
def test_id_reutilizado_globalmente(base: Database, otro_tipo: bool) -> None:
    original = creacion()
    recibir(base, original)
    nuevo = propuesta() if otro_tipo else original
    alterado = replace(
        nuevo,
        identidad=replace(nuevo.identidad, id_trabajo=UUID(int=500), id_peticion=UUID(int=501)),
        procedencia=replace(nuevo.procedencia, event_id=original.procedencia.event_id),
    )
    anterior = estado(base)
    with pytest.raises(ConflictoMensaje):
        recibir(base, alterado)
    assert estado(base) == anterior


@pytest.mark.parametrize("completa", [False, True])
@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
def test_peticion_no_pertenece_a_otro_trabajo(
    base: Database, completa: bool, resultado: DatosResultadoCotizacion
) -> None:
    recibir(base, resultado)
    if completa:
        recibir(base, creacion())
    anterior = estado(base)
    alterado = replace(
        resultado,
        identidad=replace(resultado.identidad, id_trabajo=UUID(int=600)),
        procedencia=replace(resultado.procedencia, event_id=UUID(int=601)),
    )
    with pytest.raises(ConflictoFragmentos):
        recibir(base, alterado)
    assert estado(base) == anterior


@pytest.mark.parametrize("etapa", ["preparar_entrada", "guardar_metadatos", "confirmar"])
@pytest.mark.parametrize("existente", [False, True])
def test_fallos_revierten_y_permiten_reintento(base: Database, etapa: str, existente: bool) -> None:
    if existente:
        recibir(base, creacion())
    anterior = estado(base)
    original = getattr(UnidadTrabajoSeguimientoSQL, etapa)

    def fallar(unidad: UnidadTrabajoSeguimientoSQL, *args: Any, **kwargs: Any) -> Any:
        if etapa == "confirmar":
            unidad.sesion.flush()
        else:
            original(unidad, *args, **kwargs)
        raise RuntimeError("fallo controlado")

    with patch.object(UnidadTrabajoSeguimientoSQL, etapa, fallar):
        with pytest.raises(RuntimeError, match="fallo controlado"):
            recibir(base, propuesta())
    assert estado(base) == anterior
    recibir(base, propuesta())
    assert len(estado(base)[2]) == (2 if existente else 1)


def test_fallo_commit_solo_inbox(base: Database) -> None:
    original = propuesta()
    recibir(base, original)
    equivalente = replace(
        original, procedencia=replace(original.procedencia, event_id=UUID(int=99))
    )
    anterior = estado(base)
    with patch.object(UnidadTrabajoSeguimientoSQL, "confirmar", side_effect=RuntimeError("commit")):
        with pytest.raises(RuntimeError):
            recibir(base, equivalente)
    assert estado(base) == anterior
    recibir(base, equivalente)
    assert estado(base)[:2] == anterior[:2] and len(estado(base)[2]) == 2


@pytest.mark.parametrize("revertir", [False, True])
def test_salida_sin_commit_no_reserva_peticion(base: Database, revertir: bool) -> None:
    with crear_uow(base)() as unidad:
        unidad.preparar_entrada("seguimiento.proyeccion", creacion())
        if revertir:
            unidad.revertir()
    assert not estado(base)[2]
    recibir(base, propuesta())
    assert len(estado(base)[2]) == 1


@pytest.mark.parametrize(
    "campo", ["id_solicitud", "id_partner", "id_peticion", "categoria", "tipo_red", "opuestos"]
)
@pytest.mark.parametrize("inverso", [False, True])
def test_conflictos_de_dominio_preservan_sql(base: Database, campo: str, inverso: bool) -> None:
    from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import TipoRed

    primero = creacion()
    resultado = propuesta()
    if campo.startswith("id_"):
        identificadores = replace(resultado.identidad, **{campo: UUID(int=700)})
        origen = replace(resultado.procedencia, correlacion=identificadores.id_solicitud)
        resultado = replace(resultado, identidad=identificadores, procedencia=origen)
    elif campo == "categoria":
        resultado = replace(resultado, categoria="OTRA")
    elif campo == "tipo_red":
        resultado = replace(resultado, tipo_red=TipoRed.HOMOLOGADA_PARTNER)
    fragmentos = [rechazo() if campo == "opuestos" else primero, resultado]
    if inverso:
        fragmentos.reverse()
    recibir(base, fragmentos[0])
    anterior = estado(base)
    with pytest.raises(ConflictoFragmentos):
        recibir(base, fragmentos[1])
    assert estado(base) == anterior


def test_fallo_despues_de_guardar_vista(base: Database) -> None:
    from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
        RepositorioSeguimientoSQL,
    )

    guardar = RepositorioSeguimientoSQL.guardar
    recibir(base, creacion())
    anterior = estado(base)

    def fallar(repositorio: RepositorioSeguimientoSQL, vista: VistaSeguimiento) -> None:
        guardar(repositorio, vista)
        raise RuntimeError("guardado interrumpido")

    with patch.object(RepositorioSeguimientoSQL, "guardar", fallar):
        with pytest.raises(RuntimeError):
            recibir(base, propuesta())
    assert estado(base) == anterior
    recibir(base, propuesta())
    assert len(estado(base)[2]) == 2


def test_fallo_del_commit_sql_revierte_y_cierra_sesion(base: Database) -> None:
    from sqlalchemy import Connection, event

    anterior = estado(base)

    def fallar(conexion: Connection) -> None:
        raise RuntimeError("commit SQL interrumpido")

    event.listen(base.engine, "commit", fallar)
    try:
        with pytest.raises(RuntimeError, match="commit SQL interrumpido"):
            recibir(base, propuesta())
    finally:
        event.remove(base.engine, "commit", fallar)
    assert estado(base) == anterior
    from sqlalchemy.pool import QueuePool

    assert isinstance(base.engine.pool, QueuePool)
    assert base.engine.pool.checkedout() == 0
    recibir(base, propuesta())
    assert len(estado(base)[2]) == 1


def test_restriccion_distinta_no_se_traduce_a_colision(base: Database) -> None:
    from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento

    unidad = crear_uow(base)()
    with pytest.raises(IntegrityError):
        with unidad:
            unidad.preparar_entrada("seguimiento.proyeccion", creacion())
            unidad.seguimiento.guardar(VistaSeguimiento(creacion=creacion()))
            unidad.confirmar()
    assert estado(base) == (None, None, [])
    with pytest.raises(RuntimeError, match="inactiva"):
        _ = unidad.sesion
    with pytest.raises(RuntimeError, match="inactiva"):
        _ = unidad.seguimiento


def test_sesiones_independientes_y_rollback_de_estado_completo(base: Database) -> None:
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
    from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento

    unidad = crear_uow(base)()
    with unidad:
        unidad.preparar_entrada("seguimiento.proyeccion", creacion())
        unidad.seguimiento.guardar(VistaSeguimiento(creacion=creacion()))
        unidad.guardar_metadatos(
            creacion().identidad.id_trabajo, MetadatosProyeccion(INSTANTE, INSTANTE)
        )
        unidad.sesion.flush()
        with crear_uow(base)() as otra:
            assert unidad.sesion is not otra.sesion
            assert otra.seguimiento.obtener(creacion().identidad.id_trabajo) is None
        unidad.revertir()
    assert estado(base) == (None, None, [])
    recibir(base, propuesta())
    assert len(estado(base)[2]) == 1


def test_revision_compatible_y_entero_grande_en_jsonb(base: Database) -> None:
    resultado = propuesta()
    resultado = replace(
        resultado,
        importe_menor=9_007_199_254_740_993,
        procedencia=replace(resultado.procedencia, version_contrato=2),
    )
    recibir(base, resultado)
    vista, _, entradas = estado(base)
    assert vista is not None and vista.resultado == resultado
    assert entradas[0][2]["fragmento"]["importe_menor"] == resultado.importe_menor
