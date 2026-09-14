from datetime import UTC, datetime
from uuid import UUID

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


def identidad() -> IdentidadSeguimiento:
    return IdentidadSeguimiento(
        id_trabajo=UUID(int=1),
        id_solicitud=UUID(int=2),
        id_partner=UUID(int=3),
        id_peticion=UUID(int=4),
    )


def procedencia(tipo: str, numero: int) -> Procedencia:
    return Procedencia(
        tipo=tipo,
        event_id=UUID(int=numero),
        version_contrato=1,
        instante=datetime(2026, 9, 13, tzinfo=UTC),
        correlacion=UUID(int=2),
        causacion=UUID(int=numero + 100),
    )


def creacion() -> DatosCreacion:
    return DatosCreacion(
        identidad=identidad(),
        procedencia=procedencia("TrabajoCreado.v1", 10),
        referencia_externa="PARTNER-1",
        categoria="PLOMERIA",
        tipo_solicitud=TipoSolicitud.INSTALACION,
        tipo_red=TipoRed.GENERAL_HDA,
        id_politica=UUID(int=5),
        version_politica=1,
        creado_en=datetime(2026, 9, 12, tzinfo=UTC),
    )


def propuesta() -> DatosResultadoCotizacion:
    return DatosResultadoCotizacion(
        identidad=identidad(),
        procedencia=procedencia("CotizacionRegistrada.v1", 11),
        estado=EstadoProyeccion.COTIZACION_REGISTRADA,
        version_catalogo=1,
        version_cotizacion=1,
        id_cotizacion=UUID(int=6),
        id_proveedor=UUID(int=7),
        importe_menor=15_000_000,
        moneda="COP",
        categoria="PLOMERIA",
        tipo_red=TipoRed.GENERAL_HDA,
    )


def rechazo() -> DatosResultadoCotizacion:
    return DatosResultadoCotizacion(
        identidad=identidad(),
        procedencia=procedencia("CotizacionRechazada.v1", 12),
        estado=EstadoProyeccion.COTIZACION_RECHAZADA,
        version_catalogo=1,
        version_cotizacion=1,
        motivo=MotivoRechazo.SIN_OFERTA_PARA_CATEGORIA,
    )
