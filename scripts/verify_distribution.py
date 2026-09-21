import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> None:
    project = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="seguimiento-distribution-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        environment_path = temporary_path / "environment"
        environment = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(environment_path)}
        subprocess.run(
            ["uv", "sync", "--locked", "--no-editable", "--no-dev"],
            cwd=project,
            env=environment,
            check=True,
        )
        subprocess.run(
            ["uv", "build", "--out-dir", str(temporary_path / "dist")],
            cwd=project,
            check=True,
        )
        wheel = next((temporary_path / "dist").glob("*.whl"))
        interpreter = environment_path / "bin" / "python"
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(interpreter),
                "--no-deps",
                "--reinstall",
                str(wheel),
            ],
            check=True,
        )
        verification = """
import importlib
import sys
from pathlib import Path
import seguimiento_trabajos
from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.config.database import create_database
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion, DatosResultadoCotizacion, Procedencia, IdentidadSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.dominio.servicios import combinar
from seguimiento_trabajos.seedwork.dominio.validaciones import validar_identidad
from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos
from seguimiento_trabajos.config.bootstrap import componer_seguimiento, CasosUsoSeguimiento
from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.seedwork.aplicacion.excepciones import ConflictoMensaje
from seguimiento_trabajos.modulos.seguimiento.aplicacion.unidad_trabajo import (
    UnidadTrabajoSeguimiento,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.repositorios import RepositorioSeguimiento
from seguimiento_trabajos.seedwork.aplicacion.reloj import Reloj
from seguimiento_trabajos.seedwork.aplicacion.unidad_trabajo import UnidadTrabajo
from seguimiento_trabajos.seedwork.aplicacion.reintentos import reintentar_colision
from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL
from seguimiento_trabajos.seedwork.infraestructura.serializacion import normalizar_documento
assert all(callable(component) for component in (
    UnidadTrabajo, UnidadTrabajoSQL, reintentar_colision, normalizar_documento,
))
from seguimiento_trabajos.config.persistencia import crear_uow, metadata
from seguimiento_trabajos.config.bootstrap import componer_seguimiento_sql
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import (
    guardar_fragmento, cargar_fragmento,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.unidad_trabajo import (
    UnidadTrabajoSeguimientoSQL,
)
from seguimiento_trabajos.seedwork.infraestructura.ciclos import Ciclo
from seguimiento_trabajos.seedwork.infraestructura.consumidor_pulsar import ConsumidorPulsar
from seguimiento_trabajos.seedwork.infraestructura.reloj import RelojSistema
from seguimiento_trabajos.config.bootstrap import componer_consumidores
from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.eventos import esquemas
from seguimiento_trabajos.config.procesamiento import Procesamiento
from seguimiento_trabajos.config.rutas import fuentes
from unittest.mock import Mock
base_prueba = create_database('postgresql+psycopg://test@127.0.0.1:1/test')
try:
    consumidores = componer_consumidores(base_prueba, Settings())
    assert len(consumidores) == 6 and len(esquemas()) == 3
    assert all(consumidor._cliente is None for consumidor in consumidores)
    cliente = Mock()
    efecto = Mock()
    consumidor = ConsumidorPulsar(
        'pulsar://127.0.0.1:1', fuentes(Settings())[0].topico, 'distribucion',
        Mock(), efecto, Mock(), crear_cliente=Mock(return_value=cliente),
    )
    assert consumidor.procesar_siguiente()
    efecto.assert_called_once()
    cliente.subscribe.return_value.acknowledge.assert_called_once()
    consumidor.cerrar()
finally:
    base_prueba.close()
assert set(metadata.tables) == {'inbox', 'seguimiento_trabajos', 'seguimiento_operativo', 'outbox'}
assert all(callable(component) for component in (
    crear_uow, componer_seguimiento_sql, guardar_fragmento, cargar_fragmento,
    UnidadTrabajoSeguimientoSQL,
))

package = Path(seguimiento_trabajos.__file__).resolve()
assert package.is_relative_to(Path(sys.prefix).resolve()), package
assert (package.parent / 'py.typed').is_file()
for namespace in ('modulos.seguimiento', 'seedwork'):
    for layer in ('dominio', 'aplicacion', 'infraestructura'):
        importlib.import_module(f'seguimiento_trabajos.{namespace}.{layer}')
application = create_app(Settings())
assert application.title == 'Seguimiento de Trabajos'
operation = application.openapi()['paths']['/seguimiento/trabajos/{id_trabajo}']['get']
assert set(operation['responses']) == {'200', '404', '422', '503'}
from seguimiento_trabajos.config.bootstrap import componer_consulta
from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import RespuestaSeguimiento
assert callable(componer_consulta) and callable(RespuestaSeguimiento)
assert callable(create_database)
assert all(callable(component) for component in (
    DatosCreacion, DatosResultadoCotizacion, VistaSeguimiento, Procedencia,
    IdentidadSeguimiento, combinar, validar_identidad, DatosInvalidos,
    componer_seguimiento, CasosUsoSeguimiento,
    MetadatosProyeccion, ConflictoMensaje, UnidadTrabajoSeguimiento, RepositorioSeguimiento, Reloj,
))
print(f'Installed wheel imported outside source tree: {package}')
"""
        subprocess.run([str(interpreter), "-I", "-c", verification], cwd=temporary_path, check=True)


if __name__ == "__main__":
    main()
