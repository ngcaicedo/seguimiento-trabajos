from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    EstadoProyeccion,
    MotivoRechazo,
    TipoRed,
)


@dataclass(frozen=True, kw_only=True)
class RespuestaSeguimiento:
    id_trabajo: UUID
    id_solicitud: UUID
    id_partner: UUID
    id_peticion: UUID
    estado: EstadoProyeccion
    creacion_recibida: bool
    referencia_externa: str | None
    categoria: str | None
    tipo_red: TipoRed | None
    id_cotizacion: UUID | None
    id_proveedor: UUID | None
    importe_menor: int | None
    moneda: str | None
    motivo: MotivoRechazo | None
    proyectada_en: datetime
    duracion_estimada_minutos: int | None = None
