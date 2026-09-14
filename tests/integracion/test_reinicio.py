import json
import subprocess
import sys
from dataclasses import replace
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest

from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import guardar_fragmento
from tests.integracion.datos import INSTANTE, estado
from tests.unitarias.dominio.datos import creacion, propuesta, rechazo

PROCESO = """
import json
import os
import sys
from datetime import datetime
from sqlalchemy import text
from seguimiento_trabajos.config.database import create_database
from seguimiento_trabajos.config.bootstrap import componer_seguimiento_sql
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ConflictoMensaje
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import DatosCreacion
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import cargar_fragmento

entrada = json.load(sys.stdin)
class Reloj:
    def ahora(self):
        return datetime.fromisoformat(entrada['instante'])
base = create_database(entrada['url'])
error = None
try:
    flujo = componer_seguimiento_sql(base, Reloj())
    for documento in entrada['fragmentos']:
        fragmento = cargar_fragmento(documento)
        try:
            if isinstance(fragmento, DatosCreacion):
                flujo.proyectar_creacion(fragmento)
            else:
                flujo.proyectar_resultado(fragmento)
        except ConflictoMensaje:
            error = 'ConflictoMensaje'
    with base.engine.connect() as conexion:
        inbox = conexion.scalar(text('SELECT count(*) FROM inbox'))
    print(json.dumps({'pid': os.getpid(), 'inbox': inbox, 'error': error}))
finally:
    base.close()
"""


def ejecutar_proceso(
    base: Database, fragmentos: list[DatosCreacion | DatosResultadoCotizacion], minutos: int
) -> dict[str, Any]:
    entrada = dict(
        url=base.engine.url.render_as_string(hide_password=False),
        fragmentos=[guardar_fragmento(fragmento) for fragmento in fragmentos],
        instante=(INSTANTE + timedelta(minutes=minutos)).isoformat(),
    )
    resultado = subprocess.run(
        [sys.executable, "-I", "-c", PROCESO],
        input=json.dumps(entrada),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    salida: dict[str, Any] = json.loads(resultado.stdout)
    return salida


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
def test_otro_proceso_completa_parcial_y_conserva_inbox(
    base: Database, resultado: DatosResultadoCotizacion
) -> None:
    equivalente = replace(
        resultado, procedencia=replace(resultado.procedencia, event_id=UUID(int=99))
    )
    primero = ejecutar_proceso(base, [resultado, equivalente], 0)
    parcial, fechas_parciales, _ = estado(base)
    assert parcial is not None and not parcial.creacion_recibida
    segundo = ejecutar_proceso(base, [creacion(), resultado, equivalente], 5)
    vista, fechas, entradas = estado(base)
    assert primero["pid"] != segundo["pid"] and primero["inbox"] == 2 and segundo["inbox"] == 3
    assert vista is not None and vista.creacion == creacion() and vista.resultado == resultado
    assert fechas is not None and fechas_parciales is not None
    assert fechas.primera_recepcion_en == fechas_parciales.primera_recepcion_en
    assert fechas.proyectada_en == INSTANTE + timedelta(minutes=5)
    alterado = replace(
        equivalente, procedencia=replace(equivalente.procedencia, causacion=UUID(int=555))
    )
    tercero = ejecutar_proceso(base, [alterado], 10)
    assert tercero["error"] == "ConflictoMensaje" and tercero["inbox"] == 3
    assert estado(base) == (vista, fechas, entradas)
