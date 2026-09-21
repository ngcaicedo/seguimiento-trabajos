from typing import ClassVar
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.messages import (
    TrackingInput,
    TrackingReply,
    WorkCancelled,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.mapeadores_eventos import (
    saga_document,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.outbox import record_reply
from seguimiento_trabajos.modulos.seguimiento.infraestructura.repositorios import (
    OperationalRepositorySQL,
    RepositorioSeguimientoSQL,
)
from seguimiento_trabajos.modulos.seguimiento.infraestructura.serializacion import guardar_fragmento
from seguimiento_trabajos.seedwork.infraestructura.inbox import preparar
from seguimiento_trabajos.seedwork.infraestructura.unidad_trabajo_sqlalchemy import UnidadTrabajoSQL


class UnidadTrabajoSeguimientoSQL(UnidadTrabajoSQL):
    restricciones_reintentables: ClassVar[frozenset[str]] = frozenset(
        {
            "pk_seguimiento_trabajos",
            "pk_seguimiento_operativo",
            "uq_seguimiento_peticion",
        }
    )
    _repositorio: RepositorioSeguimientoSQL

    def _crear_repositorios(self) -> None:
        self._repositorio = RepositorioSeguimientoSQL(self.sesion)
        self._operational = OperationalRepositorySQL(self.sesion)

    @property
    def seguimiento(self) -> RepositorioSeguimientoSQL:
        if not self._activa:
            raise RuntimeError("Unidad de trabajo inactiva")
        return self._repositorio

    def preparar_entrada(
        self,
        consumidor: str,
        fragmento: DatosCreacion | DatosResultadoCotizacion,
    ) -> bool:
        return preparar(
            self.sesion, consumidor, fragmento.procedencia.event_id, guardar_fragmento(fragmento)
        )

    def obtener_metadatos(self, id_trabajo: UUID) -> MetadatosProyeccion | None:
        return self.seguimiento.obtener_metadatos(id_trabajo)

    def guardar_metadatos(self, id_trabajo: UUID, metadatos: MetadatosProyeccion) -> None:
        self.seguimiento.guardar_metadatos(id_trabajo, metadatos)

    @property
    def operational(self) -> OperationalRepositorySQL:
        if not self._activa:
            raise RuntimeError("Unidad de trabajo inactiva")
        return self._operational

    def prepare_message(self, message: TrackingInput) -> bool:
        consumer = (
            "seguimiento.cancelacion-trabajo"
            if isinstance(message, WorkCancelled)
            else "seguimiento.operativo"
        )
        return preparar(self.sesion, consumer, message.message_id, saga_document(message))

    def record_reply(self, reply: TrackingReply) -> None:
        record_reply(self.sesion, reply)
