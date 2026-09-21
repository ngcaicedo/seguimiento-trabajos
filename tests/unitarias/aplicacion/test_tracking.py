from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.cancel_tracking import (
    CancelTrackingHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.open_tracking import (
    OpenTrackingHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.project_work_cancellation import (
    ProjectWorkCancellationHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import (
    CancelTracking,
    OpeningFailed,
    OpenTracking,
    WorkCancelled,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    TrackingIdentity,
    WorkCancellation,
)
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ConflictoMensaje
from tests.unitarias.aplicacion.dobles.unidad_trabajo import AlmacenMemoria, RelojFijo


def opening() -> OpenTracking:
    return OpenTracking(
        message_id=uuid4(),
        identity=TrackingIdentity(uuid4(), uuid4(), uuid4(), uuid4()),
        occurred_at=datetime.now(UTC),
        causation=uuid4(),
        quote_id=uuid4(),
    )


def cancellation(command: OpenTracking) -> CancelTracking:
    return CancelTracking(
        message_id=uuid4(),
        identity=command.identity,
        occurred_at=command.occurred_at,
        causation=command.message_id,
        reason="COMPENSACION",
        detail="Cancelar",
    )


def test_opening_reply_and_duplicate_are_atomic() -> None:
    store = AlmacenMemoria()
    command = opening()
    handler = OpenTrackingHandler(store.crear_unidad, RelojFijo(command.occurred_at))
    handler(command)
    handler(command)
    assert len(store.estado.replies) == 1
    assert store.estado.replies[0].causation == command.message_id
    with pytest.raises(ConflictoMensaje):
        handler(replace(command, quote_id=uuid4()))
    assert len(store.estado.replies) == 1


@pytest.mark.parametrize("stage", ["inbox", "guardar", "outbox", "confirmar"])
def test_failure_rolls_back_everything(stage: str) -> None:
    store = AlmacenMemoria(fallo=stage)
    command = opening()
    handler = OpenTrackingHandler(store.crear_unidad, RelojFijo(command.occurred_at))
    with pytest.raises(RuntimeError):
        handler(command)
    assert not store.estado.operational
    assert not store.estado.replies
    assert not store.estado.saga_inbox
    store.fallo = None
    handler(command)
    assert len(store.estado.replies) == 1


def test_controlled_failure_remains_failed_after_configuration_changes() -> None:
    store = AlmacenMemoria()
    command = opening()
    clock = RelojFijo(command.occurred_at)
    OpenTrackingHandler(store.crear_unidad, clock, command.identity.work_id)(command)
    OpenTrackingHandler(store.crear_unidad, clock)(command)
    assert len(store.estado.replies) == 1
    assert isinstance(store.estado.replies[0], OpeningFailed)
    assert store.estado.operational[command.identity.work_id].state is None


def test_cancel_before_open_and_cancelled_work() -> None:
    store = AlmacenMemoria()
    command = opening()
    clock = RelojFijo(command.occurred_at)
    CancelTrackingHandler(store.crear_unidad, clock)(cancellation(command))
    OpenTrackingHandler(store.crear_unidad, clock)(command)
    assert isinstance(store.estado.replies[-1], OpeningFailed)
    other = opening()
    fact = WorkCancelled(
        message_id=uuid4(),
        identity=other.identity,
        occurred_at=other.occurred_at,
        causation=uuid4(),
        fact=WorkCancellation("COMPENSACION", "Cancelar", other.occurred_at, 2),
    )
    ProjectWorkCancellationHandler(store.crear_unidad)(fact)
    OpenTrackingHandler(store.crear_unidad, clock)(other)
    assert isinstance(store.estado.replies[-1], OpeningFailed)


def test_equivalent_commands_preserve_business_identity_and_dates() -> None:
    store = AlmacenMemoria()
    command = opening()
    clock = RelojFijo(command.occurred_at)
    open_handler = OpenTrackingHandler(store.crear_unidad, clock)
    cancel_handler = CancelTrackingHandler(store.crear_unidad, clock)
    open_handler(command)
    open_handler(replace(command, message_id=uuid4()))
    original = store.estado.operational[command.identity.work_id]
    assert len(store.estado.replies) == 2
    cancel = cancellation(command)
    cancel_handler(cancel)
    cancel_handler(cancel)
    cancel_handler(replace(cancel, message_id=uuid4()))
    current = store.estado.operational[command.identity.work_id]
    assert current.tracking_id == original.tracking_id
    assert current.opened_at == original.opened_at
    assert len(store.estado.replies) == 4
    with pytest.raises(ConflictoMensaje):
        cancel_handler(replace(cancel, reason="OTRO_MOTIVO"))


def test_incompatible_saga_is_not_acknowledged_as_success() -> None:
    from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos

    store = AlmacenMemoria()
    command = opening()
    handler = OpenTrackingHandler(store.crear_unidad, RelojFijo(command.occurred_at))
    handler(command)
    with pytest.raises(ConflictoFragmentos):
        handler(
            replace(
                command, message_id=uuid4(), identity=replace(command.identity, saga_id=uuid4())
            )
        )
    assert len(store.estado.replies) == 1
    assert len(store.estado.saga_inbox) == 1
