from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE seguimiento_trabajos (
        id_trabajo UUID NOT NULL,
        id_peticion UUID NOT NULL,
        id_solicitud UUID NOT NULL,
        id_partner UUID NOT NULL,
        fragmento_creacion JSONB,
        fragmento_resultado JSONB,
        estado VARCHAR NOT NULL,
        creacion_recibida BOOLEAN NOT NULL,
        categoria VARCHAR,
        tipo_red VARCHAR,
        referencia_externa VARCHAR,
        creado_en TIMESTAMPTZ,
        primera_recepcion_en TIMESTAMPTZ NOT NULL,
        proyectada_en TIMESTAMPTZ NOT NULL,
        CONSTRAINT pk_seguimiento_trabajos PRIMARY KEY (id_trabajo),
        CONSTRAINT uq_seguimiento_peticion UNIQUE (id_peticion),
        CONSTRAINT ck_seguimiento_fragmento_presente CHECK (
            fragmento_creacion IS NOT NULL OR fragmento_resultado IS NOT NULL)
    )""")
    op.execute(
        "CREATE INDEX ix_seguimiento_fecha ON seguimiento_trabajos "
        "(primera_recepcion_en, id_trabajo)"
    )
    op.execute(
        "CREATE INDEX ix_seguimiento_partner_fecha ON seguimiento_trabajos "
        "(id_partner, primera_recepcion_en, id_trabajo)"
    )
    op.execute(
        "CREATE INDEX ix_seguimiento_estado_fecha ON seguimiento_trabajos "
        "(estado, primera_recepcion_en, id_trabajo)"
    )
    op.execute("""CREATE TABLE inbox (
        consumidor_logico VARCHAR NOT NULL,
        event_id UUID NOT NULL,
        documento JSONB NOT NULL,
        PRIMARY KEY (consumidor_logico, event_id)
    )""")


def downgrade() -> None:
    op.execute("DROP TABLE inbox")
    op.execute("DROP TABLE seguimiento_trabajos")
