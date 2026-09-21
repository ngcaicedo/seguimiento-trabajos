from collections.abc import Callable

from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.modulos.seguimiento.infraestructura.outbox import OutboxSQL
from seguimiento_trabajos.modulos.seguimiento.infraestructura.unidad_trabajo import (
    UnidadTrabajoSeguimientoSQL,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.vistas import (
    OperationalTrackingSQL,
    VistaSeguimientoSQL,
)
from seguimiento_trabajos.seedwork.infraestructura.inbox import EntradaSQL
from seguimiento_trabajos.seedwork.infraestructura.orm import BaseSQL

metadata = BaseSQL.metadata
assert VistaSeguimientoSQL.metadata is metadata and EntradaSQL.metadata is metadata


def crear_uow(base: Database) -> Callable[[], UnidadTrabajoSeguimientoSQL]:
    return lambda: UnidadTrabajoSeguimientoSQL(base.session_factory)


assert OperationalTrackingSQL.metadata is metadata and OutboxSQL.metadata is metadata
