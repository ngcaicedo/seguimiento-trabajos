from unittest.mock import patch

import pytest

from seguimiento_trabajos.config.bootstrap import componer_seguimiento
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ColisionPersistencia
from tests.unitarias.aplicacion.dobles.unidad_trabajo import (
    AlmacenMemoria,
    RelojFijo,
    UnidadTrabajoMemoria,
)
from tests.unitarias.dominio.datos import creacion


def test_reintenta_desde_inbox_con_unidad_nueva() -> None:
    almacen = AlmacenMemoria()
    fragmento = creacion()
    confirmar = UnidadTrabajoMemoria.confirmar
    intentos = 0

    def confirmar_con_colision(unidad: UnidadTrabajoMemoria) -> None:
        nonlocal intentos
        intentos += 1
        if intentos < 3:
            raise ColisionPersistencia("colision")
        confirmar(unidad)

    with patch.object(UnidadTrabajoMemoria, "confirmar", confirmar_con_colision):
        componer_seguimiento(
            almacen.crear_unidad, RelojFijo(fragmento.creado_en)
        ).proyectar_creacion(fragmento)
    assert len(almacen.unidades) == 3
    assert len({id(unidad) for unidad in almacen.unidades}) == 3
    assert len(almacen.estado.entradas) == len(almacen.estado.vistas) == 1


def test_agotamiento_propaga_sin_confirmar() -> None:
    almacen = AlmacenMemoria()
    fragmento = creacion()
    with patch.object(
        UnidadTrabajoMemoria, "confirmar", side_effect=ColisionPersistencia("colision")
    ):
        with pytest.raises(ColisionPersistencia):
            componer_seguimiento(
                almacen.crear_unidad, RelojFijo(fragmento.creado_en)
            ).proyectar_creacion(fragmento)
    assert len(almacen.unidades) == 3
    assert not almacen.estado.entradas and not almacen.estado.vistas


@pytest.mark.parametrize("error", [ValueError("conflicto"), RuntimeError("fallo tecnico")])
def test_no_reintenta_otros_errores(error: Exception) -> None:
    almacen = AlmacenMemoria()
    fragmento = creacion()
    with patch.object(UnidadTrabajoMemoria, "confirmar", side_effect=error):
        with pytest.raises(type(error)):
            componer_seguimiento(
                almacen.crear_unidad, RelojFijo(fragmento.creado_en)
            ).proyectar_creacion(fragmento)
    assert len(almacen.unidades) == 1 and not almacen.estado.entradas
