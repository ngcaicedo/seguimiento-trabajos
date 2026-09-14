from dataclasses import dataclass
from datetime import datetime

from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
    EstadoProyeccion,
    IdentidadSeguimiento,
    TipoRed,
)
from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos


@dataclass(frozen=True, kw_only=True)
class VistaSeguimiento:
    creacion: DatosCreacion | None = None
    resultado: DatosResultadoCotizacion | None = None

    def __post_init__(self) -> None:
        if self.creacion is None and self.resultado is None:
            raise DatosInvalidos("La vista requiere al menos un fragmento")
        if self.creacion is not None and not isinstance(self.creacion, DatosCreacion):
            raise DatosInvalidos("Fragmento de creacion invalido")
        if self.resultado is not None and not isinstance(self.resultado, DatosResultadoCotizacion):
            raise DatosInvalidos("Fragmento de resultado invalido")
        if self.creacion is not None and self.resultado is not None:
            if self.creacion.identidad != self.resultado.identidad:
                raise ConflictoFragmentos("Identidades incompatibles entre fragmentos")
            if self.creacion.procedencia.event_id == self.resultado.procedencia.event_id:
                raise ConflictoFragmentos("Un ID de evento no puede identificar dos hechos")
            if self.resultado.estado is EstadoProyeccion.COTIZACION_REGISTRADA and (
                self.creacion.categoria != self.resultado.categoria
                or self.creacion.tipo_red != self.resultado.tipo_red
            ):
                raise ConflictoFragmentos("Categoria o red incompatible entre fragmentos")

    @property
    def identidad(self) -> IdentidadSeguimiento:
        if self.creacion is not None:
            return self.creacion.identidad
        assert self.resultado is not None
        return self.resultado.identidad

    @property
    def estado(self) -> EstadoProyeccion:
        if self.resultado is not None:
            return self.resultado.estado
        return EstadoProyeccion.PENDIENTE_COTIZACION

    @property
    def creacion_recibida(self) -> bool:
        return self.creacion is not None

    @property
    def categoria(self) -> str | None:
        if self.creacion is not None:
            return self.creacion.categoria
        assert self.resultado is not None
        return self.resultado.categoria

    @property
    def tipo_red(self) -> TipoRed | None:
        if self.creacion is not None:
            return self.creacion.tipo_red
        assert self.resultado is not None
        return self.resultado.tipo_red

    @property
    def referencia_externa(self) -> str | None:
        return self.creacion.referencia_externa if self.creacion is not None else None

    @property
    def creado_en(self) -> datetime | None:
        return self.creacion.creado_en if self.creacion is not None else None
