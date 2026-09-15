from dataclasses import asdict

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
    Documento,
    entero,
    identidad,
    instante,
    normalizar_documento,
    objeto,
    texto,
)


def guardar_fragmento(fragmento: DatosCreacion | DatosResultadoCotizacion) -> Documento:
    datos = asdict(fragmento)
    # Preserve the canonical inbox document of historical events with unknown duration.
    if (
        isinstance(fragmento, DatosResultadoCotizacion)
        and fragmento.duracion_estimada_minutos is None
    ):
        datos.pop("duracion_estimada_minutos")
    return normalizar_documento({"version_formato": 1, "fragmento": datos})


def cargar_fragmento(documento: Documento) -> DatosCreacion | DatosResultadoCotizacion:
    if entero(documento, "version_formato") != 1:
        raise ValueError("Version de almacenamiento desconocida")
    datos = dict(objeto(documento, "fragmento"))
    identidades = objeto(datos, "identidad")
    identidad_fragmento = IdentidadSeguimiento(
        **{nombre: identidad(identidades, nombre) for nombre in identidades}
    )
    datos.pop("identidad")
    origen = dict(objeto(datos, "procedencia"))
    datos.pop("procedencia")
    for nombre in ("event_id", "correlacion", "causacion"):
        origen[nombre] = identidad(origen, nombre)
    origen["instante"] = instante(origen, "instante")
    procedencia = Procedencia(**origen)
    datos["estado"] = EstadoProyeccion(texto(datos, "estado"))
    if procedencia.tipo == "TrabajoCreado.v1":
        datos["id_politica"] = identidad(datos, "id_politica")
        datos["creado_en"] = instante(datos, "creado_en")
        datos["tipo_solicitud"] = TipoSolicitud(datos["tipo_solicitud"])
        datos["tipo_red"] = TipoRed(datos["tipo_red"])
        return DatosCreacion(identidad=identidad_fragmento, procedencia=procedencia, **datos)
    for nombre in ("id_cotizacion", "id_proveedor"):
        datos[nombre] = identidad(datos, nombre) if datos[nombre] is not None else None
    datos["tipo_red"] = TipoRed(datos["tipo_red"]) if datos["tipo_red"] is not None else None
    datos["motivo"] = MotivoRechazo(datos["motivo"]) if datos["motivo"] is not None else None
    return DatosResultadoCotizacion(identidad=identidad_fragmento, procedencia=procedencia, **datos)
