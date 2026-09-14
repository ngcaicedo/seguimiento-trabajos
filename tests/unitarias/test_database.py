from unittest.mock import Mock

import psycopg
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from seguimiento_trabajos.config.database import Database, create_database


def test_real_factory_creates_independent_sessions_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Mock(side_effect=AssertionError("unexpected database connection"))
    monkeypatch.setattr(psycopg, "connect", connection)
    database = create_database("postgresql+psycopg://test:test@127.0.0.1:1/test")
    try:
        with (
            database.session_factory() as first_session,
            database.session_factory() as second_session,
        ):
            assert first_session is not second_session
            assert first_session.bind is database.engine
            assert second_session.bind is database.engine
            first_session.info["request_id"] = "first"
            assert "request_id" not in second_session.info
    finally:
        database.close()
    connection.assert_not_called()


def test_database_close_disposes_owned_engine() -> None:
    engine = Mock(spec=Engine)
    database = Database(engine=engine, session_factory=sessionmaker())
    database.close()
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("url", ["sqlite://", "postgresql://test", "postgresql+psycopg2://test"])
def test_database_requires_explicit_psycopg_dialect(url: str) -> None:
    with pytest.raises(ValueError, match="postgresql\\+psycopg"):
        create_database(url)
