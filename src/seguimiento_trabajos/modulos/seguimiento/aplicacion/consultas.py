from typing import Protocol
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import RespuestaSeguimiento


class RepositorioLecturaSeguimiento(Protocol):
    def obtener(self, id_trabajo: UUID) -> RespuestaSeguimiento | None: ...


class RepositorioListadoSeguimiento(Protocol):
    def listar(
        self, duracion_maxima_minutos: int | None, limite: int
    ) -> list[RespuestaSeguimiento]: ...
