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

package = Path(seguimiento_trabajos.__file__).resolve()
assert package.is_relative_to(Path(sys.prefix).resolve()), package
assert (package.parent / 'py.typed').is_file()
for namespace in ('modulos.seguimiento', 'seedwork'):
    for layer in ('dominio', 'aplicacion', 'infraestructura'):
        importlib.import_module(f'seguimiento_trabajos.{namespace}.{layer}')
assert create_app(Settings()).title == 'Seguimiento de Trabajos'
assert callable(create_database)
assert all(callable(component) for component in (
    DatosCreacion, DatosResultadoCotizacion, VistaSeguimiento, Procedencia,
    IdentidadSeguimiento, combinar, validar_identidad, DatosInvalidos,
))
print(f'Installed wheel imported outside source tree: {package}')
"""
        subprocess.run([str(interpreter), "-I", "-c", verification], cwd=temporary_path, check=True)


if __name__ == "__main__":
    main()
