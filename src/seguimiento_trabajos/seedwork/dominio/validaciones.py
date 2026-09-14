from datetime import UTC, datetime
from uuid import UUID

from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos


def validar_identidad(valor: object) -> None:
    if not isinstance(valor, UUID) or valor.int == 0:
        raise DatosInvalidos("La identidad debe ser un UUID no nulo")


def validar_entero_positivo(valor: object) -> None:
    if type(valor) is not int or valor < 1:
        raise DatosInvalidos("Se requiere un entero positivo")


def validar_texto(valor: object) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise DatosInvalidos("Se requiere texto no vacio")


def normalizar_instante(valor: object) -> datetime:
    if not isinstance(valor, datetime) or valor.utcoffset() is None:
        raise DatosInvalidos("El instante debe incluir zona horaria")
    return valor.astimezone(UTC)
