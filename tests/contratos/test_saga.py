import json
import re
from pathlib import Path
from uuid import uuid4

import pytest
from pulsar.schema import AvroSchema

from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.saga import saga_schemas
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import (
    read_saga_message,
    saga_document,
)

CONTRACTS = Path(__file__).resolve().parents[2] / "docs/contratos"


@pytest.mark.parametrize("kind", list(saga_schemas()))
def test_avro_contract_and_examples(kind: str) -> None:
    record = saga_schemas()[kind]
    name = re.sub(r"(?<!^)(?=[A-Z])", "-", kind.split(".")[0]).lower() + "-v1"
    example = json.loads((CONTRACTS / (name + ".ejemplo.json")).read_text())
    assert record.schema() == json.loads((CONTRACTS / (name + ".avsc")).read_text())
    common = {
        "tipo",
        "version_contrato",
        "instante",
        "correlacion",
        "causacion",
        "id_saga",
        "id_solicitud",
        "id_trabajo",
        "id_partner",
    }
    assert common <= set(example)
    codec = AvroSchema(record)
    decoded = codec.decode(codec.encode(record(**example)))
    assert {
        field["name"]: getattr(decoded, field["name"]) for field in record.schema()["fields"]
    } == example
    if kind in {
        "AbrirSeguimientoTrabajo.v1",
        "CancelarSeguimientoTrabajo.v1",
        "TrabajoCancelado.v1",
    }:
        message = read_saga_message(decoded, kind, example["id_trabajo"])
        assert saga_document(message) == example


@pytest.mark.parametrize(
    "field,value",
    [
        ("version_contrato", 2),
        ("version_contrato", True),
        ("correlacion", str(uuid4())),
        ("id_saga", "bad"),
        ("instante", "2026-09-21T00:00:00"),
        ("command_id", "00000000-0000-0000-0000-000000000000"),
    ],
)
def test_invalid_command_is_rejected(field: str, value: object) -> None:
    data = json.loads((CONTRACTS / "abrir-seguimiento-trabajo-v1.ejemplo.json").read_text())
    data[field] = value
    with pytest.raises(ValueError):
        read_saga_message(data, "AbrirSeguimientoTrabajo.v1", data["id_trabajo"])
