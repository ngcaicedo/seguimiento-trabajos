from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos
from seguimiento_trabajos.seedwork.dominio.validaciones import (
    normalizar_instante,
    validar_entero_positivo,
    validar_identidad,
    validar_texto,
)


@pytest.mark.parametrize("valor", [None, "", UUID(int=0), 1])
def test_identidad_invalida(valor: object) -> None:
    with pytest.raises(DatosInvalidos):
        validar_identidad(valor)


@pytest.mark.parametrize("valor", [0, -1, True, 1.5, "1", None])
def test_entero_positivo_estricto(valor: object) -> None:
    with pytest.raises(DatosInvalidos):
        validar_entero_positivo(valor)


@pytest.mark.parametrize("valor", ["", "  ", None, 1])
def test_texto_invalido(valor: object) -> None:
    with pytest.raises(DatosInvalidos):
        validar_texto(valor)


@pytest.mark.parametrize("valor", [None, "2026-09-13", datetime(2026, 9, 13)])
def test_instante_requiere_fecha_con_zona(valor: object) -> None:
    with pytest.raises(DatosInvalidos):
        normalizar_instante(valor)


def test_valores_validos_y_normalizacion_preservan_significado() -> None:
    validar_identidad(UUID(int=1))
    validar_entero_positivo(1)
    validar_texto(" PLOMERIA ")
    instante = datetime(2026, 9, 13, 7, tzinfo=timezone(timedelta(hours=-5)))
    assert normalizar_instante(instante) == datetime(2026, 9, 13, 12, tzinfo=UTC)
    assert normalizar_instante(instante).tzinfo is UTC
