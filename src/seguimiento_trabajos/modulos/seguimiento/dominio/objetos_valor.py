from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos
from seguimiento_trabajos.seedwork.dominio.validaciones import (
    normalizar_instante,
    validar_entero_positivo,
    validar_identidad,
    validar_texto,
)


class EstadoProyeccion(StrEnum):
    PENDIENTE_COTIZACION = "PENDIENTE_COTIZACION"
    COTIZACION_REGISTRADA = "COTIZACION_REGISTRADA"
    COTIZACION_RECHAZADA = "COTIZACION_RECHAZADA"


class TipoRed(StrEnum):
    GENERAL_HDA = "GENERAL_HDA"
    HOMOLOGADA_PARTNER = "HOMOLOGADA_PARTNER"


class TipoSolicitud(StrEnum):
    SINIESTRO = "SINIESTRO"
    INSTALACION = "INSTALACION"


class MotivoRechazo(StrEnum):
    SIN_OFERTA_PARA_CATEGORIA = "SIN_OFERTA_PARA_CATEGORIA"
    SIN_PROVEEDOR_EN_RED = "SIN_PROVEEDOR_EN_RED"


@dataclass(frozen=True, kw_only=True)
class IdentidadSeguimiento:
    id_trabajo: UUID
    id_solicitud: UUID
    id_partner: UUID
    id_peticion: UUID

    def __post_init__(self) -> None:
        for valor in (self.id_trabajo, self.id_solicitud, self.id_partner, self.id_peticion):
            validar_identidad(valor)


@dataclass(frozen=True, kw_only=True)
class Procedencia:
    tipo: str
    event_id: UUID
    version_contrato: int
    instante: datetime
    correlacion: UUID
    causacion: UUID

    def __post_init__(self) -> None:
        if self.tipo not in (
            "TrabajoCreado.v1",
            "CotizacionRegistrada.v1",
            "CotizacionRechazada.v1",
        ):
            raise DatosInvalidos("Tipo de evento desconocido")
        for valor in (self.event_id, self.correlacion, self.causacion):
            validar_identidad(valor)
        validar_entero_positivo(self.version_contrato)
        object.__setattr__(self, "instante", normalizar_instante(self.instante))


def _validar_origen(identidad: IdentidadSeguimiento, procedencia: Procedencia, tipo: str) -> None:
    if not isinstance(identidad, IdentidadSeguimiento) or not isinstance(procedencia, Procedencia):
        raise DatosInvalidos("Identidad o procedencia invalida")
    if procedencia.tipo != tipo or procedencia.correlacion != identidad.id_solicitud:
        raise DatosInvalidos("Tipo o correlacion incompatible con el fragmento")
    if tipo != "CotizacionRegistrada.v1" and procedencia.version_contrato != 1:
        raise DatosInvalidos("Revision no soportada para este tipo de evento")


@dataclass(frozen=True, kw_only=True)
class DatosCreacion:
    identidad: IdentidadSeguimiento
    procedencia: Procedencia
    referencia_externa: str
    categoria: str
    tipo_solicitud: TipoSolicitud
    tipo_red: TipoRed
    id_politica: UUID
    version_politica: int
    creado_en: datetime
    version_trabajo: int = 1
    estado: EstadoProyeccion = EstadoProyeccion.PENDIENTE_COTIZACION

    def __post_init__(self) -> None:
        _validar_origen(self.identidad, self.procedencia, "TrabajoCreado.v1")
        validar_texto(self.referencia_externa)
        validar_texto(self.categoria)
        validar_identidad(self.id_politica)
        validar_entero_positivo(self.version_politica)
        validar_entero_positivo(self.version_trabajo)
        if self.version_trabajo != 1 or self.estado is not EstadoProyeccion.PENDIENTE_COTIZACION:
            raise DatosInvalidos("La creacion requiere version 1 y estado pendiente")
        if not isinstance(self.tipo_solicitud, TipoSolicitud) or not isinstance(
            self.tipo_red, TipoRed
        ):
            raise DatosInvalidos("Tipo de solicitud o red invalido")
        object.__setattr__(self, "creado_en", normalizar_instante(self.creado_en))


@dataclass(frozen=True, kw_only=True)
class DatosResultadoCotizacion:
    identidad: IdentidadSeguimiento
    procedencia: Procedencia
    estado: EstadoProyeccion
    version_catalogo: int
    version_cotizacion: int
    id_cotizacion: UUID | None = None
    id_proveedor: UUID | None = None
    importe_menor: int | None = None
    moneda: str | None = None
    categoria: str | None = None
    tipo_red: TipoRed | None = None
    motivo: MotivoRechazo | None = None

    def __post_init__(self) -> None:
        validar_entero_positivo(self.version_catalogo)
        validar_entero_positivo(self.version_cotizacion)
        if self.version_cotizacion != 1:
            raise DatosInvalidos("No se admite recotizacion")
        if self.estado is EstadoProyeccion.COTIZACION_REGISTRADA:
            _validar_origen(self.identidad, self.procedencia, "CotizacionRegistrada.v1")
            validar_identidad(self.id_cotizacion)
            validar_identidad(self.id_proveedor)
            validar_entero_positivo(self.importe_menor)
            validar_texto(self.categoria)
            if (
                self.moneda != "COP"
                or not isinstance(self.tipo_red, TipoRed)
                or self.motivo is not None
            ):
                raise DatosInvalidos("Propuesta requiere COP, red y ausencia de motivo")
        elif self.estado is EstadoProyeccion.COTIZACION_RECHAZADA:
            _validar_origen(self.identidad, self.procedencia, "CotizacionRechazada.v1")
            if not isinstance(self.motivo, MotivoRechazo) or any(
                valor is not None
                for valor in (
                    self.id_cotizacion,
                    self.id_proveedor,
                    self.importe_menor,
                    self.moneda,
                    self.categoria,
                    self.tipo_red,
                )
            ):
                raise DatosInvalidos("Rechazo requiere motivo y ausencia de oferta")
        else:
            raise DatosInvalidos("Estado de resultado invalido")
