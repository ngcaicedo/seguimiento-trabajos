from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import (
    OpeningFailed,
    OpenTracking,
    TrackingOpened,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OpeningRejected,
    OperationalTracking,
)
from seguimiento_trabajos.seedwork.aplicacion.reintentos import reintentar_colision
from seguimiento_trabajos.seedwork.aplicacion.reloj import Reloj


@dataclass
class OpenTrackingHandler:
    create_unit: Callable[[], UnidadTrabajoSeguimiento]
    clock: Reloj
    fail_work_id: UUID | None = None
    new_id: Callable[[], UUID] = uuid4

    @reintentar_colision
    def __call__(self, command: OpenTracking) -> None:
        with self.create_unit() as unit:
            if not unit.prepare_message(command):
                return
            tracking = unit.operational.get(command.identity.work_id) or OperationalTracking(
                command.identity
            )
            tracking.check_identity(command.identity)
            now = self.clock.ahora()
            try:
                opened = tracking.open(command.quote_id, self.new_id(), now)
                if tracking.state is None and self.fail_work_id == command.identity.work_id:
                    raise OpeningRejected("FALLO_CONTROLADO_APERTURA")
            except OpeningRejected as error:
                unit.operational.save(tracking)
                unit.record_reply(
                    OpeningFailed(
                        message_id=self.new_id(),
                        identity=command.identity,
                        occurred_at=now,
                        causation=command.message_id,
                        reason=str(error),
                        detail="No fue posible abrir el seguimiento",
                    )
                )
            else:
                assert opened.tracking_id is not None and opened.opened_at is not None
                unit.operational.save(opened)
                unit.record_reply(
                    TrackingOpened(
                        message_id=self.new_id(),
                        identity=command.identity,
                        occurred_at=now,
                        causation=command.message_id,
                        tracking_id=opened.tracking_id,
                        opened_at=opened.opened_at,
                    )
                )
            unit.confirmar()
