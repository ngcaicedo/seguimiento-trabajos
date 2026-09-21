from typing import Any

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import (
    CancelTracking,
    OpeningFailed,
    OpenTracking,
    TrackingCancelled,
    TrackingInput,
    TrackingOpened,
    TrackingReply,
    WorkCancelled,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
    EstadoProyeccion,
    IdentidadSeguimiento,
    MotivoRechazo,
    Procedencia,
    TipoRed,
    TipoSolicitud,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    TrackingIdentity,
    WorkCancellation,
)
from seguimiento_trabajos.seedwork.infraestructura.serializacion import (
    Documento,
    entero,
    identidad,
    instante,
    normalizar_documento,
    texto,
)


class MensajeInvalido(ValueError):
    def __init__(self, motivo: str, event_id: str | None = None) -> None:
        super().__init__(motivo)
        self.event_id = event_id


def leer_evento(
    registro: Any, tipo_esperado: str, clave: str
) -> DatosCreacion | DatosResultadoCotizacion:
    datos = registro if isinstance(registro, dict) else vars(registro)
    try:
        tipo = texto(datos, "tipo")
        if tipo != tipo_esperado or clave != texto(datos, "id_trabajo"):
            raise ValueError("Topico, tipo o clave incoherentes")
        identidades = IdentidadSeguimiento(
            **{
                campo: identidad(datos, campo)
                for campo in ("id_trabajo", "id_solicitud", "id_partner", "id_peticion")
            }
        )
        origen = Procedencia(
            tipo=tipo,
            event_id=identidad(datos, "event_id"),
            version_contrato=entero(datos, "version_contrato"),
            instante=instante(datos, "instante"),
            correlacion=identidad(datos, "correlacion"),
            causacion=identidad(datos, "causacion"),
        )
        if tipo == "TrabajoCreado.v1":
            return DatosCreacion(
                identidad=identidades,
                procedencia=origen,
                referencia_externa=texto(datos, "referencia_externa"),
                categoria=texto(datos, "categoria"),
                tipo_solicitud=TipoSolicitud(texto(datos, "tipo_solicitud")),
                tipo_red=TipoRed(texto(datos, "tipo_red")),
                id_politica=identidad(datos, "id_politica"),
                version_politica=entero(datos, "version_politica"),
                creado_en=instante(datos, "creado_en"),
                version_trabajo=entero(datos, "version_trabajo"),
                estado=EstadoProyeccion(texto(datos, "estado")),
            )
        if tipo == "CotizacionRegistrada.v1":
            return DatosResultadoCotizacion(
                identidad=identidades,
                procedencia=origen,
                version_catalogo=entero(datos, "version_catalogo"),
                version_cotizacion=entero(datos, "version_cotizacion"),
                estado=EstadoProyeccion.COTIZACION_REGISTRADA,
                id_cotizacion=identidad(datos, "id_cotizacion"),
                id_proveedor=identidad(datos, "id_proveedor"),
                importe_menor=entero(datos, "importe_menor"),
                duracion_estimada_minutos=(
                    entero(datos, "duracion_estimada_minutos")
                    if datos.get("duracion_estimada_minutos") is not None
                    else None
                ),
                moneda=texto(datos, "moneda"),
                categoria=texto(datos, "categoria"),
                tipo_red=TipoRed(texto(datos, "tipo_red")),
            )
        return DatosResultadoCotizacion(
            identidad=identidades,
            procedencia=origen,
            version_catalogo=entero(datos, "version_catalogo"),
            version_cotizacion=entero(datos, "version_cotizacion"),
            estado=EstadoProyeccion.COTIZACION_RECHAZADA,
            motivo=MotivoRechazo(texto(datos, "motivo")),
        )
    except (ValueError, TypeError, KeyError) as error:
        event_id = datos.get("event_id")
        raise MensajeInvalido(
            str(error), event_id if isinstance(event_id, str) else None
        ) from error


def saga_document(message: TrackingInput | TrackingReply) -> Documento:
    identity = message.identity
    document: dict[str, object] = {
        "command_id"
        if isinstance(message, (OpenTracking, CancelTracking))
        else "event_id": message.message_id,
        "tipo": message.contract,
        "version_contrato": 1,
        "instante": message.occurred_at,
        "correlacion": identity.request_id,
        "causacion": message.causation,
        "id_saga": identity.saga_id,
        "id_solicitud": identity.request_id,
        "id_trabajo": identity.work_id,
        "id_partner": identity.partner_id,
    }
    if isinstance(message, OpenTracking):
        document["id_cotizacion"] = message.quote_id
    elif isinstance(message, (CancelTracking, OpeningFailed)):
        document.update(codigo_motivo=message.reason, detalle=message.detail)
    elif isinstance(message, WorkCancelled):
        document.update(
            codigo_motivo=message.fact.reason,
            detalle=message.fact.detail,
            cancelado_en=message.fact.cancelled_at,
            version_trabajo=message.fact.work_version,
        )
    elif isinstance(message, TrackingOpened):
        document.update(id_seguimiento=message.tracking_id, abierto_en=message.opened_at)
    elif isinstance(message, TrackingCancelled):
        document.update(id_seguimiento=message.tracking_id, cancelado_en=message.cancelled_at)
    return normalizar_documento(document)


def read_saga_message(record: Any, expected_type: str, key: str) -> TrackingInput:
    data = record if isinstance(record, dict) else vars(record)
    try:
        if texto(data, "tipo") != expected_type or texto(data, "id_trabajo") != key:
            raise ValueError("Topico, tipo o clave incoherentes")
        if entero(data, "version_contrato") != 1:
            raise ValueError("Version de contrato no soportada")
        message_identity = TrackingIdentity(
            identidad(data, "id_trabajo"),
            identidad(data, "id_solicitud"),
            identidad(data, "id_partner"),
            identidad(data, "id_saga"),
        )
        if identidad(data, "correlacion") != message_identity.request_id:
            raise ValueError("Correlacion distinta de solicitud")
        message_id = identidad(
            data, "event_id" if expected_type == WorkCancelled.contract else "command_id"
        )
        occurred_at = instante(data, "instante")
        causation = identidad(data, "causacion")
        if expected_type == OpenTracking.contract:
            return OpenTracking(
                message_id=message_id,
                identity=message_identity,
                occurred_at=occurred_at,
                causation=causation,
                quote_id=identidad(data, "id_cotizacion"),
            )
        if expected_type == CancelTracking.contract:
            return CancelTracking(
                message_id=message_id,
                identity=message_identity,
                occurred_at=occurred_at,
                causation=causation,
                reason=texto(data, "codigo_motivo"),
                detail=texto(data, "detalle"),
            )
        if expected_type == WorkCancelled.contract:
            return WorkCancelled(
                message_id=message_id,
                identity=message_identity,
                occurred_at=occurred_at,
                causation=causation,
                fact=WorkCancellation(
                    texto(data, "codigo_motivo"),
                    texto(data, "detalle"),
                    instante(data, "cancelado_en"),
                    entero(data, "version_trabajo"),
                ),
            )
        raise ValueError("Tipo de mensaje no soportado")
    except (ValueError, TypeError, KeyError) as error:
        identifier = data.get("command_id", data.get("event_id"))
        raise MensajeInvalido(
            str(error), identifier if isinstance(identifier, str) else None
        ) from error
