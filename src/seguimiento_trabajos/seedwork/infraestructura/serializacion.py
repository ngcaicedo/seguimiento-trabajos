import json
from datetime import datetime
from typing import Any, cast
from uuid import UUID

Documento = dict[str, Any]


def _representar(valor: object) -> str:
    if isinstance(valor, UUID):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat()
    raise TypeError(f"Tipo no serializable: {type(valor).__name__}")


def normalizar_documento(documento: Documento) -> Documento:
    return cast(Documento, json.loads(json.dumps(documento, default=_representar)))


def texto(documento: Documento, campo: str) -> str:
    valor = documento[campo]
    if not isinstance(valor, str):
        raise ValueError(f"{campo} debe ser texto")
    return valor


def entero(documento: Documento, campo: str) -> int:
    valor = documento[campo]
    if type(valor) is not int:
        raise ValueError(f"{campo} debe ser entero")
    return valor


def objeto(documento: Documento, campo: str) -> Documento:
    valor = documento[campo]
    if not isinstance(valor, dict):
        raise ValueError(f"{campo} debe ser objeto")
    return valor


def identidad(documento: Documento, campo: str) -> UUID:
    return UUID(texto(documento, campo))


def instante(documento: Documento, campo: str) -> datetime:
    return datetime.fromisoformat(texto(documento, campo))
