from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.repositorios import RepositorioSeguimiento


class UnidadTrabajoSeguimiento(Protocol):
    @property
    def seguimiento(self) -> RepositorioSeguimiento: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        tipo_error: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None: ...

    def preparar_entrada(
        self, consumidor: str, fragmento: DatosCreacion | DatosResultadoCotizacion
    ) -> bool: ...

    def obtener_metadatos(self, id_trabajo: UUID) -> MetadatosProyeccion | None: ...

    def guardar_metadatos(self, id_trabajo: UUID, metadatos: MetadatosProyeccion) -> None: ...

    def confirmar(self) -> None: ...

    def revertir(self) -> None: ...
