from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import (
    CancelTracking,
    OpenTracking,
    WorkCancelled,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import (
    MensajeInvalido,
    leer_evento,
    read_saga_message,
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


def saga_processor(
    kind: str,
    topic: str,
    open_tracking: Callable[[OpenTracking], None],
    cancel_tracking: Callable[[CancelTracking], None],
    project_cancellation: Callable[[WorkCancelled], None],
) -> Callable[[Any], None]:
    def process(message: Any) -> None:
        if message.topic_name() != topic:
            raise MensajeInvalido("Topico inesperado")
        try:
            record = message.value()
        except Exception as error:
            raise MensajeInvalido("No se pudo decodificar el mensaje") from error
        command = read_saga_message(record, kind, message.partition_key())
        try:
            if isinstance(command, OpenTracking):
                open_tracking(command)
            elif isinstance(command, CancelTracking):
                cancel_tracking(command)
            else:
                project_cancellation(command)
        except Exception as error:
            raise ErrorProcesamiento(error, str(command.message_id)) from error

    return process
