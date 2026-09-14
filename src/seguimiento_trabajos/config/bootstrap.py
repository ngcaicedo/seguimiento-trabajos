from collections.abc import Callable
from dataclasses import dataclass

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
