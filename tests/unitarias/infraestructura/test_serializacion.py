from dataclasses import replace
from datetime import timedelta, timezone

import pytest

from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import (
    cargar_fragmento,
    guardar_fragmento,
)
from tests.unitarias.dominio.datos import creacion, propuesta, rechazo


@pytest.mark.parametrize("fragmento", [creacion(), propuesta(), rechazo()])
def test_documento_preserva_todos_los_datos(
    fragmento: DatosCreacion | DatosResultadoCotizacion,
) -> None:
    assert cargar_fragmento(guardar_fragmento(fragmento)) == fragmento


def test_revision_compatible_dinero_y_normalizacion() -> None:
    original = propuesta()
    fragmento = replace(
        original,
        importe_menor=9_007_199_254_740_993,
        procedencia=replace(
            original.procedencia,
            version_contrato=2,
            instante=original.procedencia.instante.astimezone(timezone(timedelta(hours=-5))),
        ),
    )
    documento = guardar_fragmento(fragmento)
    assert cargar_fragmento(documento) == fragmento
    assert documento["fragmento"]["importe_menor"] == fragmento.importe_menor


@pytest.mark.parametrize("campo,valor", [("importe_menor", 1.5), ("importe_menor", True)])
def test_no_coerciona_importes_invalidos(campo: str, valor: object) -> None:
    documento = guardar_fragmento(propuesta())
    documento["fragmento"][campo] = valor
    with pytest.raises(ValueError):
        cargar_fragmento(documento)
