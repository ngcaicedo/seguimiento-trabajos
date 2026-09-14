import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from seguimiento_trabajos.config.database import Database, create_database


@pytest.fixture(scope="session")
def base_integracion() -> Iterator[Database]:
    url = make_url(
        os.getenv(
            "SEGUIMIENTO_TEST_DATABASE_URL",
            "postgresql+psycopg://seguimiento:seguimiento_local@127.0.0.1:55435/seguimiento",
        )
    )
    nombre = "seguimiento_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
    try:
        with admin.connect() as conexion:
            conexion.execute(text(f'CREATE DATABASE "{nombre}"'))
    except Exception:
        admin.dispose()
        pytest.fail(
            "PostgreSQL requerido: docker compose -f docker-compose.yaml up -d --wait postgres",
            pytrace=False,
        )
    base = create_database(url.set(database=nombre).render_as_string(hide_password=False))
    try:
        configuracion = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        with base.engine.begin() as conexion:
            configuracion.attributes["connection"] = conexion
            command.upgrade(configuracion, "head")
        yield base
    finally:
        base.close()
        with admin.connect() as conexion:
            conexion.execute(text(f'DROP DATABASE "{nombre}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def base(base_integracion: Database) -> Database:
    with base_integracion.engine.begin() as conexion:
        conexion.execute(text("TRUNCATE inbox, seguimiento_trabajos"))
    return base_integracion
