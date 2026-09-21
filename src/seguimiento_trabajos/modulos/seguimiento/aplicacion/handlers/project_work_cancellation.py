from collections.abc import Callable
from dataclasses import dataclass

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import WorkCancelled
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking,
)
from seguimiento_trabajos.seedwork.aplicacion.reintentos import reintentar_colision


@dataclass
class ProjectWorkCancellationHandler:
    create_unit: Callable[[], UnidadTrabajoSeguimiento]

    @reintentar_colision
    def __call__(self, event: WorkCancelled) -> None:
        with self.create_unit() as unit:
            if not unit.prepare_message(event):
                return
            tracking = unit.operational.get(event.identity.work_id) or OperationalTracking(
                event.identity
            )
            tracking.check_identity(event.identity)
            unit.operational.save(tracking.record_work_cancellation(event.fact))
            unit.confirmar()
