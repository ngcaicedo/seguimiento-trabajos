import subprocess
import sys


def test_modelo_importa_y_valida_sin_infraestructura() -> None:
    codigo = """
import importlib.abc
import sys
import socket

def prohibir_conexion(*args, **kwargs):
    raise AssertionError('Conexion externa inesperada')
socket.socket.connect = prohibir_conexion
socket.socket.connect_ex = prohibir_conexion
socket.create_connection = prohibir_conexion
class Bloqueo(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'fastapi', 'sqlalchemy', 'psycopg', 'pulsar', 'solicitudes_partner',
            'orquestacion_trabajos', 'cotizaciones',
        }:
            raise AssertionError(fullname)
sys.meta_path.insert(0, Bloqueo())
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.dominio.servicios import combinar
from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking, TrackingIdentity,
)
from uuid import uuid4
from datetime import datetime, UTC
operational = OperationalTracking(TrackingIdentity(uuid4(), uuid4(), uuid4(), uuid4()))
assert operational.cancel(datetime.now(UTC)).state == 'CANCELADO'
assert callable(combinar)
try:
    VistaSeguimiento()
except DatosInvalidos:
    pass
else:
    raise AssertionError('Vista vacia aceptada')
"""
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
