import json
from collections.abc import Callable
from pathlib import Path

import pytest

from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.eventos import esquemas
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import leer_evento
from tests.unitarias.dominio.datos import creacion, propuesta, rechazo

CONTRATOS = Path(__file__).resolve().parents[2] / "docs/contratos"


@pytest.mark.parametrize(
    "nombre,fabrica",
    [
        ("trabajo-creado", creacion),
        ("cotizacion-registrada", propuesta),
        ("cotizacion-rechazada", rechazo),
    ],
)
def test_contrato_binario_preserva_fragmento(
    nombre: str, fabrica: Callable[[], DatosCreacion | DatosResultadoCotizacion]
) -> None:
    from pulsar.schema import AvroSchema

    registro = esquemas()[nombre]
    documento = json.loads((CONTRATOS / f"{nombre}-v1.ejemplo.json").read_text())
    schema = AvroSchema(registro)
    assert registro.schema() == json.loads((CONTRATOS / f"{nombre}-v1.avsc").read_text())
    mensaje = schema.decode(schema.encode(registro(**documento)))
    assert leer_evento(mensaje, documento["tipo"], documento["id_trabajo"]) == fabrica()


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("event_id", "no-uuid"),
        ("instante", "sin-fecha"),
        ("importe_menor", True),
        ("importe_menor", -1),
        ("correlacion", "00000000-0000-0000-0000-000000000099"),
    ],
)
def test_frontera_rechaza_datos_invalidos(campo: str, valor: object) -> None:
    documento = json.loads((CONTRATOS / "cotizacion-registrada-v1.ejemplo.json").read_text())
    documento[campo] = valor
    with pytest.raises(ValueError):
        leer_evento(documento, "CotizacionRegistrada.v1", documento["id_trabajo"])


def test_topico_tipo_y_clave_no_se_pueden_cruzar() -> None:
    documento = json.loads((CONTRATOS / "trabajo-creado-v1.ejemplo.json").read_text())
    for tipo, clave in [
        ("CotizacionRegistrada.v1", documento["id_trabajo"]),
        ("TrabajoCreado.v1", "otro"),
    ]:
        with pytest.raises(ValueError):
            leer_evento(documento, tipo, clave)
