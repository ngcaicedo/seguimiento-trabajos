from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from seguimiento_trabajos.seedwork.aplicacion.excepciones import ConflictoMensaje
from seguimiento_trabajos.seedwork.infraestructura.orm import BaseSQL
from seguimiento_trabajos.seedwork.infraestructura.serializacion import Documento


class EntradaSQL(BaseSQL):
    __tablename__ = "inbox"
    consumidor_logico: Mapped[str] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    documento: Mapped[Documento] = mapped_column(JSONB)


def preparar(sesion: Session, consumidor: str, event_id: UUID, documento: Documento) -> bool:
    if not consumidor.strip():
        raise ValueError("Consumidor vacio")
    nuevo = sesion.scalar(
        insert(EntradaSQL)
        .values(consumidor_logico=consumidor, event_id=event_id, documento=documento)
        .on_conflict_do_nothing(index_elements=[EntradaSQL.consumidor_logico, EntradaSQL.event_id])
        .returning(EntradaSQL.event_id)
    )
    if nuevo is not None:
        return True
    anterior = sesion.scalar(
        select(EntradaSQL.documento).where(
            EntradaSQL.consumidor_logico == consumidor, EntradaSQL.event_id == event_id
        )
    )
    if anterior != documento:
        raise ConflictoMensaje("Mismo mensaje con contenido diferente")
    return False
