from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.api.seguimiento import obtener_consulta
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.consultar_seguimiento import (
    ConsultarSeguimientoHandler,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores import (
    actualizar_fila,
    cargar_respuesta,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.vistas import VistaSeguimientoSQL
from seguimiento_trabajos.seedwork.aplicacion.excepciones import PersistenciaNoDisponible
from tests.unitarias.dominio.datos import creacion, identidad, propuesta, rechazo


@pytest.mark.parametrize(
    "creation,result",
    [
        (creacion(), None),
        (None, propuesta()),
        (None, rechazo()),
        (creacion(), propuesta()),
        (creacion(), rechazo()),
    ],
)
def test_get_returns_known_fields_and_explicit_nulls(
    creation: DatosCreacion | None,
    result: DatosResultadoCotizacion | None,
) -> None:
    row = VistaSeguimientoSQL()
    actualizar_fila(row, VistaSeguimiento(creacion=creation, resultado=result))
    row.proyectada_en = creacion().creado_en
    repository = Mock()
    repository.obtener.return_value = cargar_respuesta(row)
    app = create_app(Settings())
    app.dependency_overrides[obtener_consulta] = lambda: ConsultarSeguimientoHandler(repository)
    with TestClient(app) as client:
        response = client.get(f"/seguimiento/trabajos/{identidad().id_trabajo}")
    assert response.status_code == 200
    has_offer = result is not None and result.id_cotizacion is not None
    known_category = creation is not None or has_offer
    assert response.json() == {
        "id_trabajo": str(identidad().id_trabajo),
        "id_solicitud": str(identidad().id_solicitud),
        "id_partner": str(identidad().id_partner),
        "id_peticion": str(identidad().id_peticion),
        "estado": result.estado.value if result else "PENDIENTE_COTIZACION",
        "creacion_recibida": creation is not None,
        "referencia_externa": "PARTNER-1" if creation else None,
        "categoria": "PLOMERIA" if known_category else None,
        "tipo_red": "GENERAL_HDA" if known_category else None,
        "id_cotizacion": str(UUID(int=6)) if has_offer else None,
        "id_proveedor": str(UUID(int=7)) if has_offer else None,
        "importe_menor": 15_000_000 if has_offer else None,
        "moneda": "COP" if has_offer else None,
        "motivo": "SIN_OFERTA_PARA_CATEGORIA" if result and result.motivo else None,
        "proyectada_en": "2026-09-12T00:00:00Z",
    }
    repository.obtener.assert_called_once_with(identidad().id_trabajo)


def test_absence_and_invalid_ids() -> None:
    repository = Mock()
    repository.obtener.return_value = None
    app = create_app(Settings())
    app.dependency_overrides[obtener_consulta] = lambda: ConsultarSeguimientoHandler(repository)
    with TestClient(app) as client:
        assert client.get(f"/seguimiento/trabajos/{identidad().id_trabajo}").status_code == 404
        for invalid in ("invalid", str(UUID(int=0))):
            assert client.get(f"/seguimiento/trabajos/{invalid}").status_code == 422
    repository.obtener.assert_called_once_with(identidad().id_trabajo)


def test_missing_database_is_unavailable() -> None:
    with TestClient(create_app(Settings())) as client:
        assert client.get(f"/seguimiento/trabajos/{identidad().id_trabajo}").status_code == 503
        assert client.get("/health/live").status_code == 200


def test_database_failure_is_503_but_unexpected_error_propagates() -> None:
    repository = Mock()
    app = create_app(Settings())
    app.dependency_overrides[obtener_consulta] = lambda: ConsultarSeguimientoHandler(repository)
    with TestClient(app) as client:
        repository.obtener.side_effect = PersistenciaNoDisponible("private connection details")
        response = client.get(f"/seguimiento/trabajos/{identidad().id_trabajo}")
        assert response.status_code == 503
        assert "private" not in response.text
        repository.obtener.side_effect = RuntimeError("unexpected")
        with pytest.raises(RuntimeError, match="unexpected"):
            client.get(f"/seguimiento/trabajos/{identidad().id_trabajo}")
