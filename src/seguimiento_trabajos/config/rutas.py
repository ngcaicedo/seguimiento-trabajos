from dataclasses import dataclass

from seguimiento_trabajos.config.settings import Settings


@dataclass(frozen=True)
class Fuente:
    nombre: str
    tipo: str
    topico: str
    suscripcion: str


def fuentes(settings: Settings) -> tuple[Fuente, ...]:
    return (
        Fuente(
            "trabajo-creado",
            "TrabajoCreado.v1",
            settings.topico_creacion,
            "seguimiento-trabajos-v1",
        ),
        Fuente(
            "cotizacion-registrada",
            "CotizacionRegistrada.v1",
            settings.topico_registrada,
            "seguimiento-cotizacion-registrada",
        ),
        Fuente(
            "cotizacion-rechazada",
            "CotizacionRechazada.v1",
            settings.topico_rechazada,
            "seguimiento-cotizacion-rechazada-v1",
        ),
    )


def saga_sources(settings: Settings) -> tuple[Fuente, ...]:
    return (
        Fuente(
            "abrir-seguimiento-trabajo",
            "AbrirSeguimientoTrabajo.v1",
            settings.topico_apertura,
            "seguimiento-apertura-v1",
        ),
        Fuente(
            "cancelar-seguimiento-trabajo",
            "CancelarSeguimientoTrabajo.v1",
            settings.topico_cancelacion,
            "seguimiento-cancelacion-v1",
        ),
        Fuente(
            "trabajo-cancelado",
            "TrabajoCancelado.v1",
            settings.topico_trabajo_cancelado,
            "seguimiento-trabajo-cancelado-v1",
        ),
    )


def reply_topics(settings: Settings) -> dict[str, str]:
    return {
        "SeguimientoTrabajoAbierto.v1": settings.topico_abierto,
        "AperturaSeguimientoFallida.v1": settings.topico_apertura_fallida,
        "SeguimientoTrabajoCancelado.v1": settings.topico_cancelado,
    }
