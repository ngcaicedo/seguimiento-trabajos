from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos
from seguimiento_trabajos.seedwork.dominio.validaciones import (
    normalizar_instante,
    validar_entero_positivo,
    validar_identidad,
    validar_texto,
)


class TrackingState(StrEnum):
    OPEN = "ABIERTO"
    CANCELLED = "CANCELADO"


@dataclass(frozen=True)
class TrackingIdentity:
    work_id: UUID
    request_id: UUID
    partner_id: UUID
    saga_id: UUID

    def __post_init__(self) -> None:
        for value in (self.work_id, self.request_id, self.partner_id, self.saga_id):
            validar_identidad(value)


@dataclass(frozen=True)
class WorkCancellation:
    reason: str
    detail: str
    cancelled_at: datetime
    work_version: int

    def __post_init__(self) -> None:
        validar_texto(self.reason)
        validar_texto(self.detail)
        validar_entero_positivo(self.work_version)
        object.__setattr__(self, "cancelled_at", normalizar_instante(self.cancelled_at))


class OpeningRejected(Exception):
    pass


@dataclass(frozen=True)
class OperationalTracking:
    identity: TrackingIdentity
    state: TrackingState | None = None
    tracking_id: UUID | None = None
    quote_id: UUID | None = None
    opened_at: datetime | None = None
    cancelled_at: datetime | None = None
    work_cancellation: WorkCancellation | None = None

    def __post_init__(self) -> None:
        for value in (self.tracking_id, self.quote_id):
            if value is not None:
                validar_identidad(value)
        for name in ("opened_at", "cancelled_at"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, normalizar_instante(value))
        if self.state is not None and not isinstance(self.state, TrackingState):
            raise DatosInvalidos("Estado operativo invalido")
        if (self.tracking_id is None) != (self.opened_at is None) or (
            (self.quote_id is None) != (self.opened_at is None)
        ):
            raise DatosInvalidos("Apertura incompleta")
        if self.state == TrackingState.OPEN and self.opened_at is None:
            raise DatosInvalidos("Seguimiento abierto sin apertura")
        if (self.state == TrackingState.CANCELLED) != (self.cancelled_at is not None):
            raise DatosInvalidos("Cancelacion incompleta")
        if self.state is None and self.opened_at is not None:
            raise DatosInvalidos("Apertura sin estado")

    def check_identity(self, identity: TrackingIdentity) -> None:
        if self.identity != identity:
            raise ConflictoFragmentos("Identidades incompatibles")

    def open(self, quote_id: UUID, tracking_id: UUID, now: datetime) -> "OperationalTracking":
        validar_identidad(quote_id)
        if self.state == TrackingState.CANCELLED:
            raise OpeningRejected("SEGUIMIENTO_CANCELADO")
        if self.work_cancellation is not None:
            raise OpeningRejected("TRABAJO_CANCELADO")
        if self.quote_id is not None and self.quote_id != quote_id:
            raise ConflictoFragmentos("Cotizacion incompatible")
        if self.state == TrackingState.OPEN:
            return self
        return replace(
            self,
            state=TrackingState.OPEN,
            quote_id=quote_id,
            tracking_id=tracking_id,
            opened_at=now,
        )

    def cancel(self, now: datetime) -> "OperationalTracking":
        if self.state == TrackingState.CANCELLED:
            return self
        return replace(self, state=TrackingState.CANCELLED, cancelled_at=now)

    def record_work_cancellation(self, fact: WorkCancellation) -> "OperationalTracking":
        if self.work_cancellation is not None and self.work_cancellation != fact:
            raise ConflictoFragmentos("Cancelacion de trabajo contradictoria")
        return replace(self, work_cancellation=fact)
