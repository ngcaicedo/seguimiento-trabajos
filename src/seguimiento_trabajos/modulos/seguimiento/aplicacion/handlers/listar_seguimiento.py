from dataclasses import dataclass

from seguimiento_trabajos.modulos.seguimiento.aplicacion.consultas import (
    RepositorioListadoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import RespuestaSeguimiento


@dataclass(frozen=True)
class ListarSeguimientoHandler:
    repositorio: RepositorioListadoSeguimiento

    def __call__(
        self, duracion_maxima_minutos: int | None, limite: int = 100
    ) -> list[RespuestaSeguimiento]:
        if duracion_maxima_minutos is not None and duracion_maxima_minutos <= 0:
            raise ValueError("La duracion maxima debe ser positiva")
        if not 1 <= limite <= 100:
            raise ValueError("El limite debe estar entre 1 y 100")
        return self.repositorio.listar(duracion_maxima_minutos, limite)
