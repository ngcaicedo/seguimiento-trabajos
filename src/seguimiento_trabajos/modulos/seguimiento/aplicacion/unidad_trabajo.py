from typing import Protocol
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.repositorios import RepositorioSeguimiento
from seguimiento_trabajos.seedwork.aplicacion.unidad_trabajo import UnidadTrabajo


class UnidadTrabajoSeguimiento(UnidadTrabajo, Protocol):
    @property
    def seguimiento(self) -> RepositorioSeguimiento: ...

    def preparar_entrada(
        self, consumidor: str, fragmento: DatosCreacion | DatosResultadoCotizacion
    ) -> bool: ...

    def obtener_metadatos(self, id_trabajo: UUID) -> MetadatosProyeccion | None: ...

    def guardar_metadatos(self, id_trabajo: UUID, metadatos: MetadatosProyeccion) -> None: ...
