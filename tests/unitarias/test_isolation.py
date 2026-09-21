import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("configured_database", [False, True])
def test_import_and_lifespan_without_external_connections(configured_database: bool) -> None:
    script = """
import importlib.abc
import socket
import sys
from unittest.mock import patch

import psycopg

class BlockPulsar(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'pulsar' or fullname.startswith('pulsar.'):
            raise AssertionError(fullname)

sys.meta_path.insert(0, BlockPulsar())

def forbidden_connection(*args, **kwargs):
    raise AssertionError('Unexpected external connection')

with (
    patch.object(socket.socket, 'connect', forbidden_connection),
    patch.object(socket.socket, 'connect_ex', forbidden_connection),
    patch.object(socket, 'create_connection', forbidden_connection),
    patch.object(psycopg, 'connect', forbidden_connection),
):
    from seguimiento_trabajos.config.database import create_database
    from seguimiento_trabajos.api.app import create_app
    from fastapi.testclient import TestClient
    application = create_app()
    assert application.state.database is None
    with TestClient(application) as client:
        assert client.get('/health/live').json() == {
            'status': 'ok', 'service': 'seguimiento-trabajos'
        }
    assert application.state.database is None
"""
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("SEGUIMIENTO_", "PARTNER_", "PULSAR_", "PG"))
        and name != "DATABASE_URL"
    }
    if configured_database:
        environment["SEGUIMIENTO_DATABASE_URL"] = "postgresql+psycopg://test@127.0.0.1:1/test"
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_onion_dependency_direction() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src/seguimiento_trabajos/modulos/seguimiento"
    for layer in ("dominio", "aplicacion"):
        forbidden = ("infraestructura", "config", "api") + (
            ("aplicacion",) if layer == "dominio" else ()
        )
        for path in (root / layer).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                modules = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                elif isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                for module in modules:
                    assert not any(part in module.split(".") for part in forbidden), (path, module)
