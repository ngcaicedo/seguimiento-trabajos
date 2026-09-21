from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from seguimiento_trabajos.seedwork.infraestructura.orm import BaseSQL
from seguimiento_trabajos.seedwork.infraestructura.serializacion import Documento


class VistaSeguimientoSQL(BaseSQL):
    __tablename__ = "seguimiento_trabajos"
    __table_args__ = (
        PrimaryKeyConstraint("id_trabajo", name="pk_seguimiento_trabajos"),
        UniqueConstraint("id_peticion", name="uq_seguimiento_peticion"),
        CheckConstraint(
            "fragmento_creacion IS NOT NULL OR fragmento_resultado IS NOT NULL",
            name="ck_seguimiento_fragmento_presente",
        ),
        Index("ix_seguimiento_fecha", "primera_recepcion_en", "id_trabajo"),
        Index("ix_seguimiento_partner_fecha", "id_partner", "primera_recepcion_en", "id_trabajo"),
        Index("ix_seguimiento_estado_fecha", "estado", "primera_recepcion_en", "id_trabajo"),
    )
    id_trabajo: Mapped[UUID] = mapped_column(primary_key=True)
    id_peticion: Mapped[UUID]
    id_solicitud: Mapped[UUID]
    id_partner: Mapped[UUID]
    fragmento_creacion: Mapped[Documento | None] = mapped_column(JSONB(none_as_null=True))
    fragmento_resultado: Mapped[Documento | None] = mapped_column(JSONB(none_as_null=True))
    estado: Mapped[str]
    creacion_recibida: Mapped[bool]
    categoria: Mapped[str | None]
    tipo_red: Mapped[str | None]
    referencia_externa: Mapped[str | None]
    creado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    primera_recepcion_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    proyectada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OperationalTrackingSQL(BaseSQL):
    __tablename__ = "seguimiento_operativo"
    __table_args__ = (
        PrimaryKeyConstraint("id_trabajo", name="pk_seguimiento_operativo"),
        UniqueConstraint("id_seguimiento", name="uq_seguimiento_operativo_id"),
        CheckConstraint(
            "estado IS NULL OR estado IN ('ABIERTO', 'CANCELADO')", name="ck_operativo_estado"
        ),
        CheckConstraint(
            "((estado = 'CANCELADO') IS TRUE) = (cancelado_en IS NOT NULL)",
            name="ck_operativo_cancelacion",
        ),
        CheckConstraint(
            "(id_seguimiento IS NULL) = (abierto_en IS NULL) "
            "AND (id_cotizacion IS NULL) = (abierto_en IS NULL)",
            name="ck_operativo_apertura",
        ),
        CheckConstraint(
            "estado IS DISTINCT FROM 'ABIERTO' OR abierto_en IS NOT NULL",
            name="ck_operativo_abierto",
        ),
        CheckConstraint(
            "abierto_en IS NULL OR estado IS NOT NULL", name="ck_operativo_apertura_estado"
        ),
    )
    id_trabajo: Mapped[UUID] = mapped_column(primary_key=True)
    id_solicitud: Mapped[UUID]
    id_partner: Mapped[UUID]
    id_saga: Mapped[UUID]
    estado: Mapped[str | None]
    id_seguimiento: Mapped[UUID | None]
    id_cotizacion: Mapped[UUID | None]
    abierto_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelacion_trabajo: Mapped[Documento | None] = mapped_column(JSONB(none_as_null=True))
