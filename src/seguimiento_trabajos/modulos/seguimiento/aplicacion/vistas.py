from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    EstadoProyeccion,
    MotivoRechazo,
    TipoRed,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking,
    TrackingState,
)


@dataclass(frozen=True, kw_only=True)
class RespuestaSeguimiento:
    id_trabajo: UUID
    id_solicitud: UUID
    id_partner: UUID
    id_peticion: UUID
    estado: EstadoProyeccion
    creacion_recibida: bool
    referencia_externa: str | None
    categoria: str | None
    tipo_red: TipoRed | None
    id_cotizacion: UUID | None
    id_proveedor: UUID | None
    importe_menor: int | None
    moneda: str | None
    motivo: MotivoRechazo | None
    proyectada_en: datetime
    duracion_estimada_minutos: int | None = None


@dataclass(frozen=True, kw_only=True)
class OperationalView:
    id_seguimiento: UUID | None
    id_cotizacion: UUID | None
    estado: TrackingState
    abierto_en: datetime | None
    cancelado_en: datetime | None


@dataclass(frozen=True, kw_only=True)
class CancellationView:
    codigo_motivo: str
    detalle: str
    cancelado_en: datetime
    version_trabajo: int


@dataclass(frozen=True, kw_only=True)
class AttentionView:
    id_trabajo: UUID
    id_solicitud: UUID
    id_partner: UUID
    id_saga: UUID | None
    proyeccion: RespuestaSeguimiento | None
    seguimiento_operativo: OperationalView | None
    cancelacion_trabajo: CancellationView | None
    estado_trabajo: str | None


def attention_view(
    projection: RespuestaSeguimiento | None, operational: OperationalTracking | None
) -> AttentionView | None:
    if projection is None and (
        operational is None or (operational.state is None and operational.work_cancellation is None)
    ):
        return None
    identity = operational.identity if operational else None
    if identity is not None:
        work_id, request_id, partner_id = identity.work_id, identity.request_id, identity.partner_id
    else:
        assert projection is not None
        work_id, request_id, partner_id = (
            projection.id_trabajo,
            projection.id_solicitud,
            projection.id_partner,
        )
    fact = operational.work_cancellation if operational else None
    return AttentionView(
        id_trabajo=work_id,
        id_solicitud=request_id,
        id_partner=partner_id,
        id_saga=identity.saga_id if identity else None,
        proyeccion=projection,
        seguimiento_operativo=OperationalView(
            id_seguimiento=operational.tracking_id,
            id_cotizacion=operational.quote_id,
            estado=operational.state,
            abierto_en=operational.opened_at,
            cancelado_en=operational.cancelled_at,
        )
        if operational and operational.state
        else None,
        cancelacion_trabajo=CancellationView(
            codigo_motivo=fact.reason,
            detalle=fact.detail,
            cancelado_en=fact.cancelled_at,
            version_trabajo=fact.work_version,
        )
        if fact
        else None,
        estado_trabajo="CANCELADO" if fact else (projection.estado.value if projection else None),
    )
