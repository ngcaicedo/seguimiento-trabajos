from collections.abc import Callable

from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.servicios import combinar
from seguimiento_trabajos.seedwork.aplicacion.reloj import Reloj

CONSUMIDOR_PROYECCION = "seguimiento.proyeccion"


def proyectar_fragmento(
    fragmento: DatosCreacion | DatosResultadoCotizacion,
    crear_unidad: Callable[[], UnidadTrabajoSeguimiento],
    reloj: Reloj,
) -> None:
    with crear_unidad() as unidad:
        if not unidad.preparar_entrada(CONSUMIDOR_PROYECCION, fragmento):
            return
        id_trabajo = fragmento.identidad.id_trabajo
        anterior = unidad.seguimiento.obtener(id_trabajo)
        vista = combinar(anterior, fragmento)
        if vista != anterior:
            unidad.seguimiento.guardar(vista)
            metadatos = unidad.obtener_metadatos(id_trabajo)
            instante = reloj.ahora()
            unidad.guardar_metadatos(
                id_trabajo,
                MetadatosProyeccion(
                    primera_recepcion_en=(
                        metadatos.primera_recepcion_en if metadatos is not None else instante
                    ),
                    proyectada_en=instante,
                ),
            )
        unidad.confirmar()
