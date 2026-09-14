import subprocess
import sys
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from seguimiento_trabajos.seedwork.infraestructura.serializacion import normalizar_documento
from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL


class UnidadPrueba(UnidadTrabajoSQL):
    def _crear_repositorios(self) -> None:
        pass


@pytest.mark.parametrize("confirmar", [False, True])
def test_base_transaccional_cierra_recursos(confirmar: bool) -> None:
    sesion = Mock(spec=Session)
    unidad = UnidadPrueba(lambda: sesion)
    with unidad:
        assert unidad.sesion is sesion
        if confirmar:
            unidad.confirmar()
    sesion.begin.assert_called_once_with()
    sesion.close.assert_called_once_with()
    sesion.rollback.assert_called_once_with()
    assert sesion.commit.call_count == int(confirmar)
    assert sesion.flush.call_count == int(confirmar)
    with pytest.raises(RuntimeError, match="inactiva"):
        _ = unidad.sesion


def test_error_de_apertura_cierra_sesion() -> None:
    sesion = Mock(spec=Session)
    sesion.begin.side_effect = RuntimeError("apertura")
    unidad = UnidadPrueba(lambda: sesion)
    with pytest.raises(RuntimeError, match="apertura"):
        with unidad:
            raise AssertionError("No debe entrar")
    sesion.close.assert_called_once_with()
    with pytest.raises(RuntimeError, match="inactiva"):
        _ = unidad.sesion


def test_normalizacion_no_introduce_dependencias_del_modulo() -> None:
    codigo = """
import importlib.abc
import sys
from datetime import UTC, datetime
from uuid import UUID

class Bloqueo(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('seguimiento_trabajos.modulos'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Bloqueo())
from seguimiento_trabajos.seedwork.aplicacion.unidad_trabajo import UnidadTrabajo
from seguimiento_trabajos.seedwork.aplicacion.reintentos import reintentar_colision
from seguimiento_trabajos.seedwork.aplicacion.excepciones import (
    ColisionPersistencia, ConflictoMensaje,
)
from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL
from seguimiento_trabajos.seedwork.infraestructura.inbox import preparar
from seguimiento_trabajos.seedwork.infraestructura.serializacion import normalizar_documento
assert normalizar_documento({'id': UUID(int=1), 'fecha': datetime(2026, 9, 14, tzinfo=UTC)}) == {
    'id': str(UUID(int=1)), 'fecha': '2026-09-14T00:00:00+00:00',
}
"""
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_serializacion_rechaza_objetos_sin_formato() -> None:
    with pytest.raises(TypeError):
        normalizar_documento({"objeto": object()})
