from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import RespuestaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking,
    TrackingIdentity,
    TrackingState,
    WorkCancellation,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import (
    cargar_fragmento,
    guardar_fragmento,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.vistas import (
    OperationalTrackingSQL,
    VistaSeguimientoSQL,
)
from seguimiento_trabajos.seedwork.infraestructura.serializacion import (
    entero,
    instante,
    normalizar_documento,
    texto,
)


def cargar_vista(fila: VistaSeguimientoSQL) -> VistaSeguimiento:
    creacion = (
        cargar_fragmento(fila.fragmento_creacion) if fila.fragmento_creacion is not None else None
    )
    resultado = (
        cargar_fragmento(fila.fragmento_resultado) if fila.fragmento_resultado is not None else None
    )
    if creacion is not None and not isinstance(creacion, DatosCreacion):
        raise ValueError("Fragmento SQL de creacion invalido")
    if resultado is not None and not isinstance(resultado, DatosResultadoCotizacion):
        raise ValueError("Fragmento SQL de resultado invalido")
    return VistaSeguimiento(creacion=creacion, resultado=resultado)


def actualizar_fila(fila: VistaSeguimientoSQL, vista: VistaSeguimiento) -> None:
    fila.id_trabajo = vista.identidad.id_trabajo
    fila.id_peticion = vista.identidad.id_peticion
    fila.id_solicitud = vista.identidad.id_solicitud
    fila.id_partner = vista.identidad.id_partner
    fila.fragmento_creacion = (
        guardar_fragmento(vista.creacion) if vista.creacion is not None else None
    )
    fila.fragmento_resultado = (
        guardar_fragmento(vista.resultado) if vista.resultado is not None else None
    )
    fila.estado = vista.estado.value
    fila.creacion_recibida = vista.creacion_recibida
    fila.categoria = vista.categoria
    fila.tipo_red = vista.tipo_red.value if vista.tipo_red is not None else None
    fila.referencia_externa = vista.referencia_externa
    fila.creado_en = vista.creado_en


def cargar_respuesta(fila: VistaSeguimientoSQL) -> RespuestaSeguimiento:
    vista = cargar_vista(fila)
    resultado = vista.resultado
    return RespuestaSeguimiento(
        id_trabajo=vista.identidad.id_trabajo,
        id_solicitud=vista.identidad.id_solicitud,
        id_partner=vista.identidad.id_partner,
        id_peticion=vista.identidad.id_peticion,
        estado=vista.estado,
        creacion_recibida=vista.creacion_recibida,
        referencia_externa=vista.referencia_externa,
        categoria=vista.categoria,
        tipo_red=vista.tipo_red,
        id_cotizacion=resultado.id_cotizacion if resultado else None,
        id_proveedor=resultado.id_proveedor if resultado else None,
        importe_menor=resultado.importe_menor if resultado else None,
        moneda=resultado.moneda if resultado else None,
        motivo=resultado.motivo if resultado else None,
        proyectada_en=fila.proyectada_en,
        duracion_estimada_minutos=resultado.duracion_estimada_minutos if resultado else None,
    )


def load_operational(row: OperationalTrackingSQL) -> OperationalTracking:
    fact = row.cancelacion_trabajo
    return OperationalTracking(
        identity=TrackingIdentity(row.id_trabajo, row.id_solicitud, row.id_partner, row.id_saga),
        state=TrackingState(row.estado) if row.estado else None,
        tracking_id=row.id_seguimiento,
        quote_id=row.id_cotizacion,
        opened_at=row.abierto_en,
        cancelled_at=row.cancelado_en,
        work_cancellation=WorkCancellation(
            texto(fact, "codigo_motivo"),
            texto(fact, "detalle"),
            instante(fact, "cancelado_en"),
            entero(fact, "version_trabajo"),
        )
        if fact
        else None,
    )


def update_operational(row: OperationalTrackingSQL, tracking: OperationalTracking) -> None:
    row.id_trabajo = tracking.identity.work_id
    row.id_solicitud = tracking.identity.request_id
    row.id_partner = tracking.identity.partner_id
    row.id_saga = tracking.identity.saga_id
    row.estado = tracking.state.value if tracking.state else None
    row.id_seguimiento = tracking.tracking_id
    row.id_cotizacion = tracking.quote_id
    row.abierto_en = tracking.opened_at
    row.cancelado_en = tracking.cancelled_at
    fact = tracking.work_cancellation
    row.cancelacion_trabajo = (
        normalizar_documento(
            {
                "codigo_motivo": fact.reason,
                "detalle": fact.detail,
                "cancelado_en": fact.cancelled_at,
                "version_trabajo": fact.work_version,
            }
        )
        if fact
        else None
    )
