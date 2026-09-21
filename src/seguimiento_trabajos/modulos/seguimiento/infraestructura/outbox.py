from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Index, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import TrackingReply
from seguimiento_trabajos.modulos.seguimiento.infraestructura.consumidores import clasificar_error
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import (
    saga_document,
)
from seguimiento_trabajos.seedwork.infraestructura.ciclos import FalloPaso
from seguimiento_trabajos.seedwork.infraestructura.orm import BaseSQL
from seguimiento_trabajos.seedwork.infraestructura.serializacion import Documento


class OutboxSQL(BaseSQL):
    __tablename__ = "outbox"
    __table_args__ = (
        UniqueConstraint("command_id", name="uq_outbox_command"),
        Index("ix_outbox_pending", "publicado_en", "creado_en"),
    )
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    command_id: Mapped[UUID]
    tipo: Mapped[str]
    destino: Mapped[str]
    payload: Mapped[Documento] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def record_reply(session: Session, reply: TrackingReply) -> None:
    session.add(
        OutboxSQL(
            event_id=reply.message_id,
            command_id=reply.causation,
            tipo=reply.contract,
            destino="seguimiento.respuestas",
            payload=saga_document(reply),
            creado_en=reply.occurred_at,
        )
    )


class OutboxDispatcher:
    def __init__(
        self, create_session: Callable[[], Session], publish: Callable[[str, Documento], None]
    ) -> None:
        self.create_session = create_session
        self.publish = publish

    def dispatch_next(self) -> bool:
        with self.create_session() as session, session.begin():
            row = session.scalar(
                select(OutboxSQL)
                .where(OutboxSQL.publicado_en.is_(None))
                .order_by(OutboxSQL.creado_en, OutboxSQL.event_id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                return False
            self.publish(row.tipo, row.payload)
            row.publicado_en = datetime.now(UTC)
        return True

    def step(self, check_connection: Callable[[], None]) -> bool:
        try:
            check_connection()
            return self.dispatch_next()
        except FalloPaso:
            raise
        except Exception as error:
            raise FalloPaso(clasificar_error(error), {"motivo": type(error).__name__}) from error
