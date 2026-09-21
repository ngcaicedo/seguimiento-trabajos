from typing import Protocol
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento


class RepositorioSeguimiento(Protocol):
    def obtener(self, id_trabajo: UUID) -> VistaSeguimiento | None: ...

    def guardar(self, vista: VistaSeguimiento) -> None: ...


class OperationalRepository(Protocol):
    def get(self, work_id: UUID) -> OperationalTracking | None: ...
    def save(self, tracking: OperationalTracking) -> None: ...
