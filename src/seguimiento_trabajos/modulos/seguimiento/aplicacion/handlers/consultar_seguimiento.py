from dataclasses import dataclass
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.consultas import (
    RepositorioLecturaSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import RespuestaSeguimiento


@dataclass(frozen=True)
class ConsultarSeguimientoHandler:
    repositorio: RepositorioLecturaSeguimiento

    def __call__(self, id_trabajo: UUID) -> RespuestaSeguimiento | None:
        return self.repositorio.obtener(id_trabajo)
