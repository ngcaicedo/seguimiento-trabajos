from typing import Any

from pulsar.schema import Integer, Long, Record, String

from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.eventos import (
    esquemas as historical_schemas,
)


class CotizacionRegistradaV1(Record):  # type: ignore[misc]
    event_id = String(required=True)
    tipo = String(required=True)
    version_contrato = Integer(required=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_peticion = String(required=True)
    id_trabajo = String(required=True)
    id_solicitud = String(required=True)
    id_partner = String(required=True)
    version_catalogo = Integer(required=True)
    version_cotizacion = Integer(required=True)
    id_cotizacion = String(required=True)
    id_proveedor = String(required=True)
    importe_menor = Long(required=True)
    moneda = String(required=True)
    categoria = String(required=True)
    tipo_red = String(required=True)

    duracion_estimada_minutos = Integer(default=None, required_default=True)


def esquemas() -> dict[str, Any]:
    return {**historical_schemas(), "cotizacion-registrada": CotizacionRegistradaV1}
