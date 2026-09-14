from typing import Any

from pulsar.schema import Integer, Long, Record, String


class TrabajoCreadoV1(Record):  # type: ignore[misc]
    _avro_namespace = "orquestacion.eventos"

    event_id = String(required=True)
    tipo = String(default="TrabajoCreado.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_trabajo = String(required=True)
    id_solicitud = String(required=True)
    id_partner = String(required=True)
    id_peticion = String(required=True)
    referencia_externa = String(required=True)
    categoria = String(required=True)
    tipo_solicitud = String(required=True)
    tipo_red = String(required=True)
    id_politica = String(required=True)
    version_politica = Integer(required=True)
    creado_en = String(required=True)
    estado = String(default="PENDIENTE_COTIZACION", required=True, required_default=True)
    version_trabajo = Integer(default=1, required=True, required_default=True)


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


class CotizacionRechazadaV1(Record):  # type: ignore[misc]
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
    motivo = String(required=True)


def esquemas() -> dict[str, Any]:
    return {
        "trabajo-creado": TrabajoCreadoV1,
        "cotizacion-registrada": CotizacionRegistradaV1,
        "cotizacion-rechazada": CotizacionRechazadaV1,
    }
