from typing import Protocol
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import RespuestaSeguimiento


class RepositorioLecturaSeguimiento(Protocol):
    def obtener(self, id_trabajo: UUID) -> RespuestaSeguimiento | None: ...
