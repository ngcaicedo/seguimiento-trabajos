import subprocess
import sys


def test_persistencia_se_importa_sin_broker_ni_conexiones() -> None:
    codigo = """
import importlib.abc
import socket
import sys
from datetime import UTC, datetime

class Bloqueo(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'pulsar', 'fastapi', 'solicitudes_partner', 'cotizaciones', 'orquestacion_trabajos',
        }:
            raise AssertionError(fullname)
sys.meta_path.insert(0, Bloqueo())
def prohibir(*args, **kwargs):
    raise AssertionError('Conexion inesperada')
socket.socket.connect = prohibir
socket.create_connection = prohibir
import psycopg
psycopg.connect = prohibir
from seguimiento_trabajos.config.database import create_database
from seguimiento_trabajos.config.persistencia import metadata, crear_uow
from seguimiento_trabajos.config.bootstrap import componer_seguimiento_sql
class Reloj:
    def ahora(self):
        return datetime.now(UTC)
base = create_database('postgresql+psycopg://test:test@127.0.0.1:1/test')
try:
    unidad = crear_uow(base)()
    flujo = componer_seguimiento_sql(base, Reloj())
    assert set(metadata.tables) == {'inbox', 'seguimiento_trabajos'}
    assert flujo.proyectar_creacion and flujo.proyectar_resultado
finally:
    base.close()
"""
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_seedwork_mensajeria_no_importa_modulos_ni_configuracion() -> None:
    codigo = """
import importlib.abc, sys
class Bloqueo(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith((
            'seguimiento_trabajos.modulos', 'seguimiento_trabajos.config',
            'seguimiento_trabajos.api', 'pulsar',
        )):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Bloqueo())
from seguimiento_trabajos.seedwork.infraestructura.ciclos import Ciclo
from seguimiento_trabajos.seedwork.infraestructura.consumidor_pulsar import ConsumidorPulsar
from seguimiento_trabajos.seedwork.infraestructura.reloj import RelojSistema
assert RelojSistema().ahora().tzinfo is not None
"""
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo], capture_output=True, text=True, timeout=10
    )
    assert resultado.returncode == 0, resultado.stderr
