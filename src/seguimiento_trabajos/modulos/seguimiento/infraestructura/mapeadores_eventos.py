from typing import Any

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
from seguimiento_trabajos.seedwork.infraestructura.serializacion import (
    entero,
    identidad,
    instante,
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
