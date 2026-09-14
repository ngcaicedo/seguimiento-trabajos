from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import (
    MensajeInvalido,
    leer_evento,
)
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ColisionPersistencia
from seguimiento_trabajos.seedwork.infraestructura.ciclos import AccionError


class ErrorProcesamiento(Exception):
    def __init__(self, causa: Exception, event_id: str) -> None:
        super().__init__(type(causa).__name__)
        self.causa = causa
        self.event_id = event_id


def clasificar_error(error: Exception) -> AccionError:
    causa = error.causa if isinstance(error, ErrorProcesamiento) else error
    if isinstance(causa, (ColisionPersistencia, OperationalError, InterfaceError, PoolTimeout)):
        return AccionError.REINTENTAR
    return AccionError.PAUSAR


def procesador(
    tipo: str,
    topico: str,
    creacion: Callable[[DatosCreacion], None],
    resultado: Callable[[DatosResultadoCotizacion], None],
) -> Callable[[Any], None]:
    def procesar(mensaje: Any) -> None:
        if mensaje.topic_name() != topico:
            raise MensajeInvalido("Topico inesperado")
        try:
            registro = mensaje.value()
        except Exception as error:
            raise MensajeInvalido("No se pudo decodificar el mensaje") from error
        fragmento = leer_evento(registro, tipo, mensaje.partition_key())
        try:
            if isinstance(fragmento, DatosCreacion):
                creacion(fragmento)
            else:
                resultado(fragmento)
        except Exception as error:
            raise ErrorProcesamiento(error, str(fragmento.procedencia.event_id)) from error

    return procesar
