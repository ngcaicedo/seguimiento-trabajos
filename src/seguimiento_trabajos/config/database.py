from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]

    def close(self) -> None:
        self.engine.dispose()


def create_database(database_url: str) -> Database:
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("Database URL must use postgresql+psycopg")
    engine = create_engine(
        url,
        isolation_level="READ COMMITTED",
        pool_timeout=1,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 2,
            "options": "-c statement_timeout=1000 -c lock_timeout=500 -c transaction_timeout=2000",
            "tcp_user_timeout": 2000,
        },
    )
    return Database(engine=engine, session_factory=sessionmaker(bind=engine))
