from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.servicios import combinar
from tests.unitarias.aplicacion.dobles.unidad_trabajo import AlmacenMemoria
from tests.unitarias.dominio.datos import creacion, propuesta


@pytest.mark.parametrize("salida", ["sin_confirmar", "excepcion", "revertir", "confirmar_falla"])
def test_transaccion_aisla_vista_inbox_y_metadatos(salida: str) -> None:
    almacen = AlmacenMemoria()
    original = creacion()
    with almacen.crear_unidad() as unidad:
        unidad.seguimiento.guardar(combinar(None, original))
        unidad.preparar_entrada("seguimiento.proyeccion", original)
        unidad.confirmar()
    anterior = deepcopy(almacen.estado)
    try:
        with almacen.crear_unidad() as unidad:
            resultado = propuesta()
            unidad.seguimiento.guardar(combinar(unidad.seguimiento.obtener(UUID(int=1)), resultado))
            unidad.preparar_entrada("seguimiento.proyeccion", resultado)
            ahora = datetime(2026, 9, 14, tzinfo=UTC)
            unidad.guardar_metadatos(UUID(int=1), MetadatosProyeccion(ahora, ahora))
            with almacen.crear_unidad() as observador:
                assert observador.seguimiento.obtener(UUID(int=1)) == combinar(None, original)
                assert observador.obtener_metadatos(UUID(int=1)) is None
            if salida == "excepcion":
                raise RuntimeError("Interrupcion")
            if salida == "revertir":
                unidad.revertir()
            if salida == "confirmar_falla":
                almacen.fallo = "confirmar"
                unidad.confirmar()
    except RuntimeError:
        assert salida in {"excepcion", "confirmar_falla"}
    assert almacen.estado == anterior
    assert almacen.confirmaciones == 1


def test_referencia_provisional_no_puede_modificar_el_estado_confirmado() -> None:
    almacen = AlmacenMemoria()
    with almacen.crear_unidad() as unidad:
        vista = combinar(None, creacion())
        unidad.seguimiento.guardar(vista)
        provisional = unidad.estado_activo()
        repositorio = unidad.seguimiento
        unidad.confirmar()
    provisional.vistas.clear()
    assert almacen.estado.vistas == {UUID(int=1): vista}
    with pytest.raises(RuntimeError, match="inactiva"):
        repositorio.guardar(combinar(vista, propuesta()))


def test_rollback_no_reserva_peticion_para_un_trabajo_fallido() -> None:
    almacen = AlmacenMemoria()
    with almacen.crear_unidad() as unidad:
        unidad.seguimiento.guardar(combinar(None, creacion()))
    otro = replace(creacion(), identidad=replace(creacion().identidad, id_trabajo=UUID(int=99)))
    with almacen.crear_unidad() as unidad:
        unidad.seguimiento.guardar(combinar(None, otro))
        unidad.confirmar()
    assert set(almacen.estado.vistas) == {UUID(int=99)}
