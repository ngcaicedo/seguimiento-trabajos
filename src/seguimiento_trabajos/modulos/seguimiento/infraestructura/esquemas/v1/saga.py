from typing import Any

from pulsar.schema import Integer, Record, String


class AbrirSeguimientoTrabajoV1(Record):  # type: ignore[misc]
    _avro_namespace = "orquestacion.eventos"
    command_id = String(required=True)
    tipo = String(default="AbrirSeguimientoTrabajo.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_saga = String(required=True)
    id_solicitud = String(required=True)
    id_trabajo = String(required=True)
    id_partner = String(required=True)
    id_cotizacion = String(required=True)


class CancelarSeguimientoTrabajoV1(Record):  # type: ignore[misc]
    _avro_namespace = "orquestacion.eventos"
    command_id = String(required=True)
    tipo = String(default="CancelarSeguimientoTrabajo.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_saga = String(required=True)
    id_solicitud = String(required=True)
    id_trabajo = String(required=True)
    id_partner = String(required=True)
    codigo_motivo = String(required=True)
    detalle = String(required=True)


class TrabajoCanceladoV1(Record):  # type: ignore[misc]
    _avro_namespace = "orquestacion.eventos"
    event_id = String(required=True)
    tipo = String(default="TrabajoCancelado.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_saga = String(required=True)
    id_solicitud = String(required=True)
    id_trabajo = String(required=True)
    id_partner = String(required=True)
    codigo_motivo = String(required=True)
    detalle = String(required=True)
    cancelado_en = String(required=True)
    version_trabajo = Integer(required=True)


class SeguimientoTrabajoAbiertoV1(Record):  # type: ignore[misc]
    _avro_namespace = "seguimiento.eventos"
    event_id = String(required=True)
    tipo = String(default="SeguimientoTrabajoAbierto.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_saga = String(required=True)
    id_solicitud = String(required=True)
    id_trabajo = String(required=True)
    id_partner = String(required=True)
    id_seguimiento = String(required=True)
    abierto_en = String(required=True)


class AperturaSeguimientoFallidaV1(Record):  # type: ignore[misc]
    _avro_namespace = "seguimiento.eventos"
    event_id = String(required=True)
    tipo = String(default="AperturaSeguimientoFallida.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_saga = String(required=True)
    id_solicitud = String(required=True)
    id_trabajo = String(required=True)
    id_partner = String(required=True)
    codigo_motivo = String(required=True)
    detalle = String(required=True)


class SeguimientoTrabajoCanceladoV1(Record):  # type: ignore[misc]
    _avro_namespace = "seguimiento.eventos"
    event_id = String(required=True)
    tipo = String(default="SeguimientoTrabajoCancelado.v1", required=True, required_default=True)
    version_contrato = Integer(default=1, required=True, required_default=True)
    instante = String(required=True)
    correlacion = String(required=True)
    causacion = String(required=True)
    id_saga = String(required=True)
    id_solicitud = String(required=True)
    id_trabajo = String(required=True)
    id_partner = String(required=True)
    id_seguimiento = String(default=None)
    cancelado_en = String(required=True)


def saga_schemas() -> dict[str, Any]:
    return {
        "AbrirSeguimientoTrabajo.v1": AbrirSeguimientoTrabajoV1,
        "CancelarSeguimientoTrabajo.v1": CancelarSeguimientoTrabajoV1,
        "TrabajoCancelado.v1": TrabajoCanceladoV1,
        "SeguimientoTrabajoAbierto.v1": SeguimientoTrabajoAbiertoV1,
        "AperturaSeguimientoFallida.v1": AperturaSeguimientoFallidaV1,
        "SeguimientoTrabajoCancelado.v1": SeguimientoTrabajoCanceladoV1,
    }
