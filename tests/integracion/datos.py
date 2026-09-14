from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from seguimiento_trabajos.config.bootstrap import componer_seguimiento_sql
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.persistencia import crear_uow
from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from tests.unitarias.aplicacion.dobles.unidad_trabajo import RelojFijo
from tests.unitarias.dominio.datos import identidad

INSTANTE = datetime(2026, 9, 14, tzinfo=UTC)


def recibir(
    base: Database,
    fragmento: DatosCreacion | DatosResultadoCotizacion,
    instante: datetime = INSTANTE,
) -> None:
    flujo = componer_seguimiento_sql(base, RelojFijo(instante))
    if isinstance(fragmento, DatosCreacion):
        flujo.proyectar_creacion(fragmento)
    else:
        flujo.proyectar_resultado(fragmento)


def estado(base: Database) -> tuple[VistaSeguimiento | None, MetadatosProyeccion | None, list[Any]]:
    with crear_uow(base)() as unidad:
        vista = unidad.seguimiento.obtener(identidad().id_trabajo)
        metadatos = unidad.obtener_metadatos(identidad().id_trabajo)
    with base.engine.connect() as conexion:
        entradas = list(
            conexion.execute(
                text("SELECT consumidor_logico, event_id, documento FROM inbox ORDER BY event_id")
            ).tuples()
        )
    return vista, metadatos, entradas
