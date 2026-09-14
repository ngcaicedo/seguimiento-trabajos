from dataclasses import replace

from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import (
    ConflictoFragmentos,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos


def combinar(
    vista: VistaSeguimiento | None,
    fragmento: DatosCreacion | DatosResultadoCotizacion,
) -> VistaSeguimiento:
    """Crea o completa una vista sin modificar la anterior, en cualquier orden de llegada.

    Una creación tardía conserva el resultado de cotización. Un duplicado
    devuelve la vista original y mantiene el primer fragmento y su procedencia:
    mismo ID exige contenido y procedencia idénticos; nuevo ID exige los mismos
    datos de negocio.

    Lanza DatosInvalidos ante tipos incorrectos y ConflictoFragmentos ante
    identidades, categoría/red o hechos contradictorios, incluidos propuesta
    y rechazo para la misma petición.

    Solo compara los datos recibidos: no persiste, consulta inbox ni confirma
    mensajes. Fechas y versiones de otros servicios no deciden qué conservar.
    """
    if not isinstance(fragmento, (DatosCreacion, DatosResultadoCotizacion)):
        raise DatosInvalidos("Fragmento invalido")
    if vista is not None and not isinstance(vista, VistaSeguimiento):
        raise DatosInvalidos("Vista invalida")
    if vista is None:
        if isinstance(fragmento, DatosCreacion):
            return VistaSeguimiento(creacion=fragmento)
        return VistaSeguimiento(resultado=fragmento)
    if vista.identidad != fragmento.identidad:
        raise ConflictoFragmentos("Identidad incompatible con la vista")
    anterior = vista.creacion if isinstance(fragmento, DatosCreacion) else vista.resultado
    if anterior is not None:
        if anterior.procedencia.tipo != fragmento.procedencia.tipo:
            raise ConflictoFragmentos("Resultados opuestos para la misma peticion")
        if anterior.procedencia.event_id == fragmento.procedencia.event_id:
            if anterior != fragmento:
                raise ConflictoFragmentos("Mismo ID de evento con contenido diferente")
        elif replace(fragmento, procedencia=anterior.procedencia) != anterior:
            raise ConflictoFragmentos("Mismo hecho con contenido empresarial diferente")
        return vista
    if isinstance(fragmento, DatosCreacion):
        return replace(vista, creacion=fragmento)
    return replace(vista, resultado=fragmento)
