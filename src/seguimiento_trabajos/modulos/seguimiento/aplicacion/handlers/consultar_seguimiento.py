from dataclasses import dataclass
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.consultas import (
    AttentionReader,
    RepositorioLecturaSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import (
    AttentionView,
    RespuestaSeguimiento,
)


@dataclass(frozen=True)
class ConsultarSeguimientoHandler:
    repositorio: RepositorioLecturaSeguimiento

    def __call__(self, id_trabajo: UUID) -> RespuestaSeguimiento | None:
        return self.repositorio.obtener(id_trabajo)


@dataclass(frozen=True)
class GetAttentionHandler:
    repository: AttentionReader

    def __call__(self, work_id: UUID) -> AttentionView | None:
        return self.repository.get_attention(work_id)
