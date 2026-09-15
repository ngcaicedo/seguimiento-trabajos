from dataclasses import replace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import guardar_fragmento
from tests.integracion.datos import recibir
from tests.unitarias.dominio.datos import creacion, propuesta


def test_duration_survives_late_creation_duplicates_and_filters(base: Database) -> None:
    expected = []
    for duration in (30, 90, None):
        result = propuesta()
        identity = replace(result.identidad, id_trabajo=uuid4(), id_peticion=uuid4())
        result = replace(
            result,
            identidad=identity,
            procedencia=replace(result.procedencia, event_id=uuid4(), version_contrato=2),
            duracion_estimada_minutos=duration,
        )
        creation = replace(
            creacion(),
            identidad=identity,
            procedencia=replace(creacion().procedencia, event_id=uuid4()),
        )
        recibir(base, result)
        recibir(base, creation)
        recibir(base, result)
        expected.append((str(identity.id_trabajo), duration))
    with TestClient(
        create_app(Settings(database_url=base.engine.url.render_as_string(hide_password=False)))
    ) as client:
        for identifier, duration in expected:
            response = client.get("/seguimiento/trabajos/" + identifier)
            assert response.status_code == 200
            assert response.json()["duracion_estimada_minutos"] == duration
            assert response.json()["creacion_recibida"] is True
        response = client.get("/seguimiento/trabajos?duracion_maxima_minutos=60")
        assert response.status_code == 200
        assert [row["id_trabajo"] for row in response.json()] == [expected[0][0]]
        assert len(client.get("/seguimiento/trabajos").json()) == 3
        assert len(client.get("/seguimiento/trabajos?limite=1").json()) == 1
        for query in (
            "duracion_maxima_minutos=0",
            "duracion_maxima_minutos=-1",
            "limite=0",
            "limite=101",
        ):
            assert client.get("/seguimiento/trabajos?" + query).status_code == 422
    with base.engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM inbox")) == 6


def test_legacy_document_and_inbox_remain_readable(base: Database) -> None:
    result = propuesta()
    document = guardar_fragmento(result)
    assert "duracion_estimada_minutos" not in document["fragmento"]
    recibir(base, result)
    with base.engine.connect() as connection:
        before = connection.execute(text("SELECT documento FROM inbox")).scalar_one()
    recibir(base, result)
    with base.engine.connect() as connection:
        assert connection.execute(text("SELECT documento FROM inbox")).scalar_one() == before
    with TestClient(
        create_app(Settings(database_url=base.engine.url.render_as_string(hide_password=False)))
    ) as client:
        assert (
            client.get("/seguimiento/trabajos/" + str(result.identidad.id_trabajo)).json()[
                "duracion_estimada_minutos"
            ]
            is None
        )
