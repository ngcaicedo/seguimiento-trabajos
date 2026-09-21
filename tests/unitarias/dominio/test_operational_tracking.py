from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OpeningRejected,
    OperationalTracking,
    TrackingIdentity,
    WorkCancellation,
)


def test_open_cancel_preserves_identity_and_dates() -> None:
    identity = TrackingIdentity(uuid4(), uuid4(), uuid4(), uuid4())
    now = datetime.now(UTC)
    quote, tracking = uuid4(), uuid4()
    opened = OperationalTracking(identity).open(quote, tracking, now)
    assert opened.open(quote, uuid4(), now + timedelta(seconds=1)) == opened
    cancelled = opened.cancel(now)
    assert cancelled.tracking_id == tracking
    assert cancelled.cancel(now + timedelta(seconds=1)) == cancelled
    with pytest.raises(OpeningRejected, match="SEGUIMIENTO_CANCELADO"):
        cancelled.open(quote, uuid4(), now)


def test_cancel_before_open_and_work_cancel_before_creation() -> None:
    identity = TrackingIdentity(uuid4(), uuid4(), uuid4(), uuid4())
    now = datetime.now(UTC)
    cancelled = OperationalTracking(identity).cancel(now)
    assert cancelled.tracking_id is None
    with pytest.raises(OpeningRejected):
        cancelled.open(uuid4(), uuid4(), now)
    fact = WorkCancellation("CANCELACION_SAGA", "Compensacion", now, 2)
    projected = OperationalTracking(identity).record_work_cancellation(fact)
    assert projected.state is None
    assert projected.record_work_cancellation(fact) == projected
    with pytest.raises(OpeningRejected, match="TRABAJO_CANCELADO"):
        projected.open(uuid4(), uuid4(), now)


def test_opening_with_changed_quote_is_conflict() -> None:
    identity = TrackingIdentity(uuid4(), uuid4(), uuid4(), uuid4())
    now = datetime.now(UTC)
    opened = OperationalTracking(identity).open(uuid4(), uuid4(), now)
    with pytest.raises(ConflictoFragmentos):
        opened.open(uuid4(), uuid4(), now)
