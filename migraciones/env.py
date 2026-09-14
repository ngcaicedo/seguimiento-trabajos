import os

from alembic import context
from sqlalchemy import Connection

from seguimiento_trabajos.config.database import create_database
from seguimiento_trabajos.config.persistencia import metadata


def ejecutar(conexion: Connection) -> None:
    context.configure(connection=conexion, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


conexion = context.config.attributes.get("connection")
if conexion is not None:
    ejecutar(conexion)
else:
    base = create_database(os.environ["SEGUIMIENTO_DATABASE_URL"])
    try:
        with base.engine.connect() as conexion:
            ejecutar(conexion)
    finally:
        base.close()
