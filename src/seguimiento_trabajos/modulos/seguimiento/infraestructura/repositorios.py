from collections.abc import Callable
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy.orm import Session

from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import (
    AttentionView,
    RespuestaSeguimiento,
    attention_view,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.operational_tracking import (
    OperationalTracking,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores import (
    actualizar_fila,
    cargar_respuesta,
    cargar_vista,
    load_operational,
    update_operational,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.vistas import (
    OperationalTrackingSQL,
    VistaSeguimientoSQL,
)
from seguimiento_trabajos.seedwork.aplicacion.excepciones import PersistenciaNoDisponible


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


class RepositorioLecturaSeguimientoSQL:
    def __init__(self, crear_sesion: Callable[[], Session]) -> None:
        self.crear_sesion = crear_sesion

    def obtener(self, id_trabajo: UUID) -> RespuestaSeguimiento | None:
        try:
            with self.crear_sesion() as sesion:
                fila = sesion.scalar(
                    select(VistaSeguimientoSQL).where(VistaSeguimientoSQL.id_trabajo == id_trabajo)
                )
                return cargar_respuesta(fila) if fila is not None else None
        except (OperationalError, TimeoutError) as error:
            raise PersistenciaNoDisponible("Persistencia no disponible") from error

    def listar(
        self, duracion_maxima_minutos: int | None, limite: int
    ) -> list[RespuestaSeguimiento]:
        consulta = select(VistaSeguimientoSQL)
        if duracion_maxima_minutos is not None:
            duracion = VistaSeguimientoSQL.fragmento_resultado["fragmento"][
                "duracion_estimada_minutos"
            ].as_integer()
            consulta = consulta.where(duracion <= duracion_maxima_minutos)
        consulta = consulta.order_by(
            VistaSeguimientoSQL.primera_recepcion_en.desc(), VistaSeguimientoSQL.id_trabajo
        ).limit(limite)
        try:
            with self.crear_sesion() as sesion:
                return [cargar_respuesta(fila) for fila in sesion.scalars(consulta)]
        except (OperationalError, TimeoutError) as error:
            raise PersistenciaNoDisponible("Persistencia no disponible") from error

    def get_attention(self, work_id: UUID) -> AttentionView | None:
        try:
            with self.crear_sesion() as session:
                statement = (
                    select(VistaSeguimientoSQL, OperationalTrackingSQL)
                    .join(
                        OperationalTrackingSQL,
                        VistaSeguimientoSQL.id_trabajo == OperationalTrackingSQL.id_trabajo,
                        full=True,
                    )
                    .where(
                        or_(
                            VistaSeguimientoSQL.id_trabajo == work_id,
                            OperationalTrackingSQL.id_trabajo == work_id,
                        )
                    )
                )
                row = session.execute(statement).one_or_none()
                if row is None:
                    return None
                projection, operational = row
                return attention_view(
                    cargar_respuesta(projection) if projection else None,
                    load_operational(operational) if operational else None,
                )
        except (OperationalError, TimeoutError) as error:
            raise PersistenciaNoDisponible("Persistencia no disponible") from error


class OperationalRepositorySQL:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.rows: dict[UUID, OperationalTrackingSQL | None] = {}

    def get(self, work_id: UUID) -> OperationalTracking | None:
        if work_id not in self.rows:
            self.rows[work_id] = self.session.scalar(
                select(OperationalTrackingSQL)
                .where(OperationalTrackingSQL.id_trabajo == work_id)
                .with_for_update()
            )
        row = self.rows[work_id]
        return load_operational(row) if row is not None else None

    def save(self, tracking: OperationalTracking) -> None:
        work_id = tracking.identity.work_id
        self.get(work_id)
        row = self.rows[work_id]
        if row is None:
            row = OperationalTrackingSQL()
            self.session.add(row)
            self.rows[work_id] = row
        update_operational(row, tracking)
