from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    TrackingIdentity,
    WorkCancellation,
)
from seguimiento_trabajos.seedwork.dominio.validaciones import (
    normalizar_instante,
    validar_identidad,
    validar_texto,
)


@dataclass(frozen=True, kw_only=True)
class SagaMessage:
    message_id: UUID
    identity: TrackingIdentity
    occurred_at: datetime
    causation: UUID
    contract: ClassVar[str]

    def __post_init__(self) -> None:
        validar_identidad(self.message_id)
        validar_identidad(self.causation)
        object.__setattr__(self, "occurred_at", normalizar_instante(self.occurred_at))


@dataclass(frozen=True, kw_only=True)
class OpenTracking(SagaMessage):
    contract: ClassVar[str] = "AbrirSeguimientoTrabajo.v1"
    quote_id: UUID

    def __post_init__(self) -> None:
        super().__post_init__()
        validar_identidad(self.quote_id)


@dataclass(frozen=True, kw_only=True)
class CancelTracking(SagaMessage):
    contract: ClassVar[str] = "CancelarSeguimientoTrabajo.v1"
    reason: str
    detail: str

    def __post_init__(self) -> None:
        super().__post_init__()
        validar_texto(self.reason)
        validar_texto(self.detail)


@dataclass(frozen=True, kw_only=True)
class WorkCancelled(SagaMessage):
    contract: ClassVar[str] = "TrabajoCancelado.v1"
    fact: WorkCancellation


@dataclass(frozen=True, kw_only=True)
class TrackingOpened(SagaMessage):
    contract: ClassVar[str] = "SeguimientoTrabajoAbierto.v1"
    tracking_id: UUID
    opened_at: datetime


@dataclass(frozen=True, kw_only=True)
class OpeningFailed(SagaMessage):
    contract: ClassVar[str] = "AperturaSeguimientoFallida.v1"
    reason: str
    detail: str


@dataclass(frozen=True, kw_only=True)
class TrackingCancelled(SagaMessage):
    contract: ClassVar[str] = "SeguimientoTrabajoCancelado.v1"
    tracking_id: UUID | None
    cancelled_at: datetime


TrackingInput = OpenTracking | CancelTracking | WorkCancelled
TrackingReply = TrackingOpened | OpeningFailed | TrackingCancelled
