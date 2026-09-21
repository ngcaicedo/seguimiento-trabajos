import subprocess
import sys


def test_aplicacion_y_bootstrap_se_ejecutan_sin_infraestructura() -> None:
    codigo = """
import importlib.abc
import sys
import socket
from datetime import UTC, datetime
from uuid import UUID

def prohibir_conexion(*args, **kwargs):
    raise AssertionError('Conexion inesperada')
socket.socket.connect = prohibir_conexion
socket.socket.connect_ex = prohibir_conexion
socket.create_connection = prohibir_conexion

class Bloqueo(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {
            'fastapi', 'sqlalchemy', 'psycopg', 'pulsar', 'solicitudes_partner',
            'orquestacion_trabajos', 'cotizaciones', 'httpx', 'httpx2', 'requests',
        }:
            raise AssertionError(fullname)
sys.meta_path.insert(0, Bloqueo())
from seguimiento_trabajos.config.bootstrap import componer_seguimiento
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion, DatosResultadoCotizacion, IdentidadSeguimiento, Procedencia,
    TipoRed, TipoSolicitud, EstadoProyeccion, MotivoRechazo,
)
class Unidad:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def preparar_entrada(self, consumidor, fragmento):
        return True
    @property
    def seguimiento(self):
        return self
    def obtener(self, id_trabajo):
        return None
    def guardar(self, vista):
        self.vista = vista
    def obtener_metadatos(self, id_trabajo):
        return None
    def guardar_metadatos(self, id_trabajo, metadatos):
        self.metadatos = metadatos
    def confirmar(self):
        self.confirmada = True
class Reloj:
    def ahora(self):
        return datetime(2026, 9, 14, tzinfo=UTC)
unidades = []
def crear_unidad():
    unidad = Unidad()
    unidades.append(unidad)
    return unidad
flujo = componer_seguimiento(crear_unidad, Reloj())
assert not unidades
identidad = IdentidadSeguimiento(
    id_trabajo=UUID(int=1), id_solicitud=UUID(int=2),
    id_partner=UUID(int=3), id_peticion=UUID(int=4),
)
def origen(tipo, numero):
    return Procedencia(tipo=tipo, event_id=UUID(int=numero), version_contrato=1,
        instante=Reloj().ahora(), correlacion=UUID(int=2), causacion=UUID(int=10))
flujo.proyectar_creacion(DatosCreacion(
    identidad=identidad, procedencia=origen('TrabajoCreado.v1', 5),
    referencia_externa='REF', categoria='PLOMERIA', tipo_solicitud=TipoSolicitud.INSTALACION,
    tipo_red=TipoRed.GENERAL_HDA, id_politica=UUID(int=6), version_politica=1,
    creado_en=Reloj().ahora(),
))
flujo.proyectar_resultado(DatosResultadoCotizacion(
    identidad=identidad, procedencia=origen('CotizacionRechazada.v1', 7),
    estado=EstadoProyeccion.COTIZACION_RECHAZADA, version_catalogo=1,
    version_cotizacion=1, motivo=MotivoRechazo.SIN_OFERTA_PARA_CATEGORIA,
))
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.open_tracking import (
    OpenTrackingHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.cancel_tracking import (
    CancelTrackingHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion import messages
assert OpenTrackingHandler and CancelTrackingHandler and messages.OpenTracking
assert len(unidades) == 2
assert all(unidad.confirmada for unidad in unidades)
"""
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", codigo],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
