from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import (
    cargar_fragmento,
    guardar_fragmento,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.vistas import VistaSeguimientoSQL


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
