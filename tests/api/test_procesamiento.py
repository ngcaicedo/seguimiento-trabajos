import pytest
from fastapi.testclient import TestClient

from seguimiento_trabajos.api.app import create_app
from seguimiento_trabajos.config.settings import Settings


def test_readiness_no_declara_operativo_el_modo_tecnico() -> None:
    with TestClient(create_app(Settings())) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 503


def test_modo_operativo_requiere_base() -> None:
    with pytest.raises(ValueError):
        Settings(processing_enabled=True)


def test_configuracion_operativa_desde_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEGUIMIENTO_PROCESSING_ENABLED", "true")
    monkeypatch.setenv("SEGUIMIENTO_DATABASE_URL", "postgresql+psycopg://test")
    assert Settings.from_environment().processing_enabled
    monkeypatch.setenv("SEGUIMIENTO_PROCESSING_ENABLED", "quizas")
    with pytest.raises(ValueError):
        Settings.from_environment()


def test_error_al_iniciar_segundo_hilo_cierra_el_primero(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    from seguimiento_trabajos.config import procesamiento
    from seguimiento_trabajos.config.database import Database
    from seguimiento_trabajos.seedwork.infraestructura.ciclos import Ciclo

    consumidores = [Mock(suscripcion=str(indice)) for indice in range(3)]
    for consumidor in consumidores:
        consumidor.procesar_siguiente.return_value = False
    monkeypatch.setattr(procesamiento, "componer_consumidores", lambda *_: consumidores)
    original = Ciclo.iniciar
    iniciados: list[Ciclo] = []

    def iniciar(ciclo: Ciclo) -> None:
        if iniciados:
            raise RuntimeError("inicio segundo hilo")
        iniciados.append(ciclo)
        original(ciclo)

    monkeypatch.setattr(Ciclo, "iniciar", iniciar)
    base = Mock(spec=Database)
    with pytest.raises(RuntimeError, match="segundo hilo"):
        with TestClient(
            create_app(
                Settings(database_url="postgresql+psycopg://test", processing_enabled=True),
                lambda _: base,
            )
        ):
            pass
    assert len(iniciados) == 1 and not iniciados[0].hilo.is_alive()
    consumidores[0].cerrar.assert_called_once()
    base.close.assert_called_once()
