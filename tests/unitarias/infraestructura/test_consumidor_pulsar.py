from unittest.mock import Mock

import pytest

from seguimiento_trabajos.seedwork.infraestructura.ciclos import AccionError, FalloPaso
from seguimiento_trabajos.seedwork.infraestructura.consumidor_pulsar import ConsumidorPulsar


def crear_consumidor(procesar: Mock, clasificar: Mock) -> tuple[ConsumidorPulsar, Mock]:
    transporte = Mock()
    consumidor = ConsumidorPulsar(
        "pulsar://localhost:6650",
        "persistent://public/default/prueba",
        "prueba",
        Mock(),
        procesar,
        clasificar,
        crear_cliente=Mock(return_value=transporte),
    )
    return consumidor, transporte


def test_procesamiento_termina_antes_del_ack() -> None:
    pasos: list[str] = []
    procesar = Mock(side_effect=lambda _: pasos.append("commit"))
    consumidor, cliente = crear_consumidor(procesar, Mock())
    cliente.subscribe.return_value.acknowledge.side_effect = lambda _: pasos.append("ack")
    assert consumidor.procesar_siguiente()
    assert pasos == ["commit", "ack"]
    consumidor.cerrar()
    cliente.close.assert_called_once()


@pytest.mark.parametrize("accion", list(AccionError))
def test_error_no_recibe_ack_y_solo_transitorio_recibe_nack(accion: AccionError) -> None:
    consumidor, cliente = crear_consumidor(
        Mock(side_effect=ValueError("invalid")), Mock(return_value=accion)
    )
    with pytest.raises(FalloPaso) as fallo:
        consumidor.procesar_siguiente()
    assert fallo.value.accion == accion
    cliente.subscribe.return_value.acknowledge.assert_not_called()
    assert cliente.subscribe.return_value.negative_acknowledge.call_count == int(
        accion == AccionError.REINTENTAR
    )
    consumidor.cerrar()


def test_fallo_ack_conserva_efecto_y_reconecta() -> None:
    procesar = Mock()
    consumidor, cliente = crear_consumidor(procesar, Mock())
    cliente.subscribe.return_value.acknowledge.side_effect = RuntimeError("broker")
    with pytest.raises(FalloPaso) as fallo:
        consumidor.procesar_siguiente()
    assert fallo.value.accion == AccionError.REINTENTAR
    procesar.assert_called_once()
    cliente.close.assert_called_once()


def test_apertura_fallida_cierra_cliente() -> None:
    consumidor, cliente = crear_consumidor(Mock(), Mock())
    cliente.subscribe.side_effect = RuntimeError("broker")
    with pytest.raises(FalloPaso):
        consumidor.procesar_siguiente()
    cliente.close.assert_called_once()


def test_timeout_de_apertura_no_se_confunde_con_topico_vacio() -> None:
    import pulsar

    consumidor, cliente = crear_consumidor(Mock(), Mock())
    cliente.subscribe.side_effect = pulsar.Timeout()
    with pytest.raises(FalloPaso) as fallo:
        consumidor.procesar_siguiente()
    assert fallo.value.accion == AccionError.REINTENTAR


def test_error_de_schema_en_apertura_pausa() -> None:
    import pulsar

    consumidor, cliente = crear_consumidor(Mock(), Mock())
    cliente.subscribe.side_effect = pulsar.IncompatibleSchema()
    with pytest.raises(FalloPaso) as fallo:
        consumidor.procesar_siguiente()
    assert fallo.value.accion == AccionError.PAUSAR


def test_fallo_nack_cierra_para_reentrega_y_no_confirma() -> None:
    consumidor, cliente = crear_consumidor(
        Mock(side_effect=ValueError()), Mock(return_value=AccionError.REINTENTAR)
    )
    cliente.subscribe.return_value.negative_acknowledge.side_effect = ConnectionError()
    with pytest.raises(FalloPaso):
        consumidor.procesar_siguiente()
    cliente.close.assert_called_once()
    cliente.subscribe.return_value.acknowledge.assert_not_called()


def test_timeout_vacio_es_normal() -> None:
    import pulsar

    consumidor, cliente = crear_consumidor(Mock(), Mock())
    cliente.subscribe.return_value.receive.side_effect = pulsar.Timeout()
    assert consumidor.procesar_siguiente() is False
    cliente.subscribe.return_value.acknowledge.assert_not_called()
    consumidor.cerrar()


def test_agotamiento_de_pool_sql_es_transitorio() -> None:
    from sqlalchemy.exc import TimeoutError as PoolTimeout

    from seguimiento_trabajos.modulos.seguimiento.infraestructura.consumidores import (
        clasificar_error,
    )

    assert clasificar_error(PoolTimeout()) == AccionError.REINTENTAR
