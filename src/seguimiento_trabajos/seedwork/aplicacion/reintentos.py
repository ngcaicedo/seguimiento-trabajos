from collections.abc import Callable
from functools import wraps

from seguimiento_trabajos.seedwork.aplicacion.excepciones import ColisionPersistencia

MAXIMOS_INTENTOS = 3


def reintentar_colision[**Parametros, Resultado](
    operacion: Callable[Parametros, Resultado],
) -> Callable[Parametros, Resultado]:
    @wraps(operacion)
    def ejecutar(*argumentos: Parametros.args, **opciones: Parametros.kwargs) -> Resultado:
        for _intento in range(MAXIMOS_INTENTOS - 1):
            try:
                return operacion(*argumentos, **opciones)
            except ColisionPersistencia:
                continue
        return operacion(*argumentos, **opciones)

    return ejecutar
