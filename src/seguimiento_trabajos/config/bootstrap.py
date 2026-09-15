from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.consultar_seguimiento import (
    ConsultarSeguimientoHandler,
)

if TYPE_CHECKING:
    from seguimiento_trabajos.config.database import Database
    from seguimiento_trabajos.config.settings import Settings
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.listar_seguimiento import (
        ListarSeguimientoHandler,
    )
    from seguimiento_trabajos.seedwork.infraestructura.consumidor_pulsar import ConsumidorPulsar

from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.proyectar_creacion import (
    ProyectarCreacionHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.proyectar_resultado import (
    ProyectarResultadoHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class CasosUsoSeguimiento:
    proyectar_creacion: ProyectarCreacionHandler
    proyectar_resultado: ProyectarResultadoHandler


def componer_seguimiento(
    crear_unidad: Callable[[], UnidadTrabajoSeguimiento], reloj: Reloj
) -> CasosUsoSeguimiento:
    return CasosUsoSeguimiento(
        proyectar_creacion=ProyectarCreacionHandler(crear_unidad, reloj),
        proyectar_resultado=ProyectarResultadoHandler(crear_unidad, reloj),
    )


def componer_seguimiento_sql(base: "Database", reloj: Reloj) -> CasosUsoSeguimiento:
    from seguimiento_trabajos.config.persistencia import crear_uow

    return componer_seguimiento(crear_uow(base), reloj)


def componer_consumidores(base: "Database", settings: "Settings") -> list["ConsumidorPulsar"]:
    from pulsar.schema import AvroSchema

    from seguimiento_trabajos.config.rutas import fuentes
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.consumidores import (
        clasificar_error,
        procesador,
    )
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v2.eventos import (
        esquemas,
    )
    from seguimiento_trabajos.seedwork.infraestructura.consumidor_pulsar import ConsumidorPulsar
    from seguimiento_trabajos.seedwork.infraestructura.reloj import RelojSistema

    casos = componer_seguimiento_sql(base, RelojSistema())
    registros = esquemas()
    return [
        ConsumidorPulsar(
            settings.pulsar_url,
            fuente.topico,
            fuente.suscripcion,
            AvroSchema(registros[fuente.nombre]),
            procesador(
                fuente.tipo, fuente.topico, casos.proyectar_creacion, casos.proyectar_resultado
            ),
            clasificar_error,
            recepcion_ms=settings.recepcion_ms,
            reentrega_ms=settings.reentrega_ms,
        )
        for fuente in fuentes(settings)
    ]


def componer_consulta(base: "Database") -> ConsultarSeguimientoHandler:
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
        RepositorioLecturaSeguimientoSQL,
    )

    return ConsultarSeguimientoHandler(RepositorioLecturaSeguimientoSQL(base.session_factory))


def componer_listado(base: "Database") -> "ListarSeguimientoHandler":
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.listar_seguimiento import (
        ListarSeguimientoHandler,
    )
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
        RepositorioLecturaSeguimientoSQL,
    )

    return ListarSeguimientoHandler(RepositorioLecturaSeguimientoSQL(base.session_factory))
