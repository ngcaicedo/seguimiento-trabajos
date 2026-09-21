from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import (
    CancelTracking,
    TrackingCancelled,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking,
)
from seguimiento_trabajos.seedwork.aplicacion.reintentos import reintentar_colision
from seguimiento_trabajos.seedwork.aplicacion.reloj import Reloj


@dataclass
class CancelTrackingHandler:
    create_unit: Callable[[], UnidadTrabajoSeguimiento]
    clock: Reloj
    new_id: Callable[[], UUID] = uuid4

    @reintentar_colision
    def __call__(self, command: CancelTracking) -> None:
        with self.create_unit() as unit:
            if not unit.prepare_message(command):
                return
            tracking = unit.operational.get(command.identity.work_id) or OperationalTracking(
                command.identity
            )
            tracking.check_identity(command.identity)
            now = self.clock.ahora()
            cancelled = tracking.cancel(now)
            assert cancelled.cancelled_at is not None
            unit.operational.save(cancelled)
            unit.record_reply(
                TrackingCancelled(
                    message_id=self.new_id(),
                    identity=command.identity,
                    occurred_at=now,
                    causation=command.message_id,
                    tracking_id=cancelled.tracking_id,
                    cancelled_at=cancelled.cancelled_at,
                )
            )
            unit.confirmar()
