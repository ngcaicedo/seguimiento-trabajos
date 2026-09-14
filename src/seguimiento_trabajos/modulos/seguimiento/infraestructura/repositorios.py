from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores import (
    actualizar_fila,
    cargar_vista,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.vistas import VistaSeguimientoSQL


class RepositorioSeguimientoSQL:
    def __init__(self, sesion: Session) -> None:
        self.sesion = sesion
        self._filas: dict[UUID, VistaSeguimientoSQL | None] = {}

    def _obtener_fila(self, id_trabajo: UUID) -> VistaSeguimientoSQL | None:
        if id_trabajo not in self._filas:
            self._filas[id_trabajo] = self.sesion.scalar(
                select(VistaSeguimientoSQL)
                .where(VistaSeguimientoSQL.id_trabajo == id_trabajo)
                .with_for_update()
            )
        return self._filas[id_trabajo]

    def obtener(self, id_trabajo: UUID) -> VistaSeguimiento | None:
        fila = self._obtener_fila(id_trabajo)
        return cargar_vista(fila) if fila is not None else None

    def guardar(self, vista: VistaSeguimiento) -> None:
        propietario = self.sesion.scalar(
            select(VistaSeguimientoSQL.id_trabajo).where(
                VistaSeguimientoSQL.id_peticion == vista.identidad.id_peticion
            )
        )
        if propietario is not None and propietario != vista.identidad.id_trabajo:
            raise ConflictoFragmentos("Peticion asociada a otro trabajo")
        fila = self._obtener_fila(vista.identidad.id_trabajo)
        if fila is None:
            fila = VistaSeguimientoSQL()
            self.sesion.add(fila)
            self._filas[vista.identidad.id_trabajo] = fila
        actualizar_fila(fila, vista)

    def obtener_metadatos(self, id_trabajo: UUID) -> MetadatosProyeccion | None:
        fila = self._obtener_fila(id_trabajo)
        if fila is None or fila.primera_recepcion_en is None:
            return None
        return MetadatosProyeccion(fila.primera_recepcion_en, fila.proyectada_en)

    def guardar_metadatos(self, id_trabajo: UUID, metadatos: MetadatosProyeccion) -> None:
        fila = self._obtener_fila(id_trabajo)
        if fila is None:
            raise ValueError("Vista ausente para metadatos")
        fila.primera_recepcion_en = metadatos.primera_recepcion_en
        fila.proyectada_en = metadatos.proyectada_en
