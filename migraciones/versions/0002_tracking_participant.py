from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE seguimiento_operativo (
        id_trabajo UUID CONSTRAINT pk_seguimiento_operativo PRIMARY KEY,
        id_solicitud UUID NOT NULL, id_partner UUID NOT NULL, id_saga UUID NOT NULL,
        estado VARCHAR, id_seguimiento UUID CONSTRAINT uq_seguimiento_operativo_id UNIQUE,
        id_cotizacion UUID, abierto_en TIMESTAMPTZ, cancelado_en TIMESTAMPTZ,
        cancelacion_trabajo JSONB,
        CONSTRAINT ck_operativo_estado CHECK (estado IS NULL OR estado IN ('ABIERTO','CANCELADO')),
        CONSTRAINT ck_operativo_cancelacion CHECK (
            ((estado = 'CANCELADO') IS TRUE) = (cancelado_en IS NOT NULL)),
        CONSTRAINT ck_operativo_apertura CHECK (
            (id_seguimiento IS NULL) = (abierto_en IS NULL)
            AND (id_cotizacion IS NULL) = (abierto_en IS NULL)),
        CONSTRAINT ck_operativo_abierto CHECK (
            estado IS DISTINCT FROM 'ABIERTO' OR abierto_en IS NOT NULL),
        CONSTRAINT ck_operativo_apertura_estado CHECK (abierto_en IS NULL OR estado IS NOT NULL)
    )""")
    op.execute("""CREATE TABLE outbox (
        event_id UUID PRIMARY KEY, command_id UUID NOT NULL CONSTRAINT uq_outbox_command UNIQUE,
        tipo VARCHAR NOT NULL, destino VARCHAR NOT NULL, payload JSONB NOT NULL,
        creado_en TIMESTAMPTZ NOT NULL, publicado_en TIMESTAMPTZ
    )""")
    op.execute("CREATE INDEX ix_outbox_pending ON outbox (publicado_en, creado_en)")


def downgrade() -> None:
    op.execute("DROP TABLE outbox")
    op.execute("DROP TABLE seguimiento_operativo")
