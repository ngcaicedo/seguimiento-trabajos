from collections.abc import Callable
from dataclasses import dataclass

from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.proyectar_fragmento import (
    proyectar_fragmento,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import DatosResultadoCotizacion
from seguimiento_trabajos.seedwork.aplicacion.reloj import Reloj


@dataclass(frozen=True)
class ProyectarResultadoHandler:
    crear_unidad: Callable[[], UnidadTrabajoSeguimiento]
    reloj: Reloj

    def __call__(self, fragmento: DatosResultadoCotizacion) -> None:
        proyectar_fragmento(fragmento, self.crear_unidad, self.reloj)
