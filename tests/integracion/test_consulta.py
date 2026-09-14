from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.config.bootstrap import componer_consulta
from seguimiento_trabajos.config.database import Database, create_database
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.seedwork.aplicacion.excepciones import PersistenciaNoDisponible
from tests.integracion.datos import estado, recibir
from tests.unitarias.dominio.datos import identidad, propuesta


def test_read_uses_own_session_and_never_changes_projection(base: Database) -> None:
    recibir(base, propuesta())
    before = estado(base)
    query = componer_consulta(base)
    assert query(uuid4()) is None
    with base.session_factory() as writing:
        writing.execute(text("SELECT * FROM seguimiento_trabajos FOR UPDATE"))
        response = query(identidad().id_trabajo)
        assert response is not None and response.importe_menor == 15_000_000
    settings = Settings(database_url=base.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 503
        assert client.get(f"/seguimiento/trabajos/{identidad().id_trabajo}").status_code == 200
    assert estado(base) == before


def test_connection_failure_is_translated() -> None:
    database = create_database("postgresql+psycopg://test@127.0.0.1:1/test")
    try:
        with pytest.raises(PersistenciaNoDisponible):
            componer_consulta(database)(identidad().id_trabajo)
    finally:
        database.close()
