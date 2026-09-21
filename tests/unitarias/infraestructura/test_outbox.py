from unittest.mock import Mock

import pytest
from sqlalchemy.exc import OperationalError

from seguimiento_trabajos.modulos.seguimiento.infraestructura.outbox import OutboxDispatcher
from seguimiento_trabajos.seedwork.infraestructura.ciclos import AccionError, FalloPaso


@pytest.mark.parametrize(
    "error,expected",
    [
        (OperationalError("SELECT", {}, Exception("DB unavailable")), AccionError.REINTENTAR),
        (ValueError("Invalid stored reply"), AccionError.PAUSAR),
    ],
)
def test_dispatch_step_classifies_errors(error: Exception, expected: AccionError) -> None:
    session_factory = Mock(side_effect=error)
    dispatcher = OutboxDispatcher(session_factory, Mock())
    with pytest.raises(FalloPaso) as raised:
        dispatcher.step(Mock())
    assert raised.value.accion == expected
    assert raised.value.__cause__ is error


def test_disconnected_publisher_preserves_recovery_and_leaves_outbox_untouched() -> None:
    session_factory = Mock()
    dispatcher = OutboxDispatcher(session_factory, Mock())
    transport_error = FalloPaso(AccionError.REINTENTAR, {"motivo": "NotConnected"})
    with pytest.raises(FalloPaso) as raised:
        dispatcher.step(Mock(side_effect=transport_error))
    assert raised.value is transport_error
    session_factory.assert_not_called()
