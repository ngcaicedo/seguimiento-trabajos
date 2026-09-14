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
