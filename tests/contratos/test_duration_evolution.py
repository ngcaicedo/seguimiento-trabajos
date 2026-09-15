import io
import json
from pathlib import Path
from typing import Any

import fastavro
import pytest
from pulsar.schema import AvroSchema

from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import DatosResultadoCotizacion
from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.eventos import (
    CotizacionRegistradaV1 as HistoricalQuotation,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v2.eventos import (
    CotizacionRegistradaV1 as CurrentQuotation,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import leer_evento


@pytest.mark.parametrize("writer", [HistoricalQuotation, CurrentQuotation])
@pytest.mark.parametrize("reader", [HistoricalQuotation, CurrentQuotation])
def test_both_contract_revisions_preserve_identity(writer: Any, reader: Any) -> None:
    document = json.loads(
        (
            Path(__file__).parents[2] / "docs/contratos/cotizacion-registrada-v1.ejemplo.json"
        ).read_text()
    )
    if writer is CurrentQuotation:
        document.update(version_contrato=2, duracion_estimada_minutos=30)
    encoded = AvroSchema(writer).encode(writer(**document))
    decoded = fastavro.schemaless_reader(io.BytesIO(encoded), writer.schema(), reader.schema())
    fragment = leer_evento(decoded, document["tipo"], document["id_trabajo"])
    assert isinstance(fragment, DatosResultadoCotizacion)
    assert str(fragment.identidad.id_trabajo) == document["id_trabajo"]
    assert fragment.duracion_estimada_minutos == (
        30 if writer is reader is CurrentQuotation else None
    )


@pytest.mark.parametrize("duration", [0, -1, True, 1.5, "30"])
def test_invalid_duration_is_rejected(duration: object) -> None:
    document = json.loads(
        (
            Path(__file__).parents[2] / "docs/contratos/cotizacion-registrada-v1.ejemplo.json"
        ).read_text()
    )
    document.update(version_contrato=2, duracion_estimada_minutos=duration)
    with pytest.raises(ValueError):
        leer_evento(document, document["tipo"], document["id_trabajo"])
