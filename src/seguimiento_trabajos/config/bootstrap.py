from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING

from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.consultar_seguimiento import (
    ConsultarSeguimientoHandler,
)
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

if TYPE_CHECKING:
    from seguimiento_trabajos.config.database import Database
    from seguimiento_trabajos.config.settings import Settings
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.consultar_seguimiento import (
        GetAttentionHandler,
    )
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.listar_seguimiento import (
        ListarSeguimientoHandler,
    )
    from seguimiento_trabajos.seedwork.infraestructura.ciclos import Ciclo
    from seguimiento_trabajos.seedwork.infraestructura.consumidor_pulsar import ConsumidorPulsar


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

    from seguimiento_trabajos.config.rutas import fuentes, saga_sources
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
    consumers = [
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
    from seguimiento_trabajos.config.persistencia import crear_uow
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers import (
        project_work_cancellation,
    )
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.cancel_tracking import (
        CancelTrackingHandler,
    )
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.open_tracking import (
        OpenTrackingHandler,
    )
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.consumidores import saga_processor
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.saga import (
        saga_schemas,
    )

    factory = crear_uow(base)
    clock = RelojSistema()
    open_tracking = OpenTrackingHandler(factory, clock, settings.fail_opening_work_id)
    cancel_tracking = CancelTrackingHandler(factory, clock)
    project_cancellation = project_work_cancellation.ProjectWorkCancellationHandler(factory)
    schemas = saga_schemas()
    consumers.extend(
        ConsumidorPulsar(
            settings.pulsar_url,
            source.topico,
            source.suscripcion,
            AvroSchema(schemas[source.tipo]),
            saga_processor(
                source.tipo, source.topico, open_tracking, cancel_tracking, project_cancellation
            ),
            clasificar_error,
            recepcion_ms=settings.recepcion_ms,
            reentrega_ms=settings.reentrega_ms,
        )
        for source in saga_sources(settings)
    )
    return consumers


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


def compose_outbox(base: "Database", settings: "Settings") -> "Ciclo":
    from seguimiento_trabajos.config.rutas import reply_topics
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.despachadores import (
        TrackingPublisher,
    )
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.outbox import OutboxDispatcher
    from seguimiento_trabajos.seedwork.infraestructura.ciclos import Ciclo

    publisher = TrackingPublisher(settings.pulsar_url, reply_topics(settings))
    dispatcher = OutboxDispatcher(base.session_factory, publisher.publish)

    return Ciclo(
        "seguimiento-outbox",
        partial(dispatcher.step, publisher.check_connection),
        publisher.close,
        settings.pausa_reintento,
    )


def compose_attention(base: "Database") -> "GetAttentionHandler":
    from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.consultar_seguimiento import (
        GetAttentionHandler,
    )
    from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
        RepositorioLecturaSeguimientoSQL,
    )

    return GetAttentionHandler(RepositorioLecturaSeguimientoSQL(base.session_factory))
