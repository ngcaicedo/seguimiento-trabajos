from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from types import TracebackType
from typing import Self
from uuid import UUID

from seguimiento_trabajos.modulos.seguimiento.aplicacion.excepciones import ConflictoMensaje
from seguimiento_trabajos.modulos.seguimiento.aplicacion.metadatos import MetadatosProyeccion
from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento


@dataclass
class EstadoMemoria:
    vistas: dict[UUID, VistaSeguimiento] = field(default_factory=dict)
    entradas: dict[tuple[str, UUID], DatosCreacion | DatosResultadoCotizacion] = field(
        default_factory=dict
    )
    metadatos: dict[UUID, MetadatosProyeccion] = field(default_factory=dict)


@dataclass
class AlmacenMemoria:
    estado: EstadoMemoria = field(default_factory=EstadoMemoria)
    fallo: str | None = None
    confirmaciones: int = 0
    guardados: int = 0
    unidades: list[UnidadTrabajoMemoria] = field(default_factory=list)

    def crear_unidad(self) -> UnidadTrabajoMemoria:
        unidad = UnidadTrabajoMemoria(self)
        self.unidades.append(unidad)
        return unidad


@dataclass
class RelojFijo:
    instante: datetime
    llamadas: int = 0

    def ahora(self) -> datetime:
        self.llamadas += 1
        return self.instante


class RepositorioMemoria:
    def __init__(self, unidad: UnidadTrabajoMemoria) -> None:
        self.unidad = unidad

    def obtener(self, id_trabajo: UUID) -> VistaSeguimiento | None:
        return self.unidad.estado_activo().vistas.get(id_trabajo)

    def guardar(self, vista: VistaSeguimiento) -> None:
        estado = self.unidad.estado_activo()
        for anterior in estado.vistas.values():
            if (
                anterior.identidad.id_peticion == vista.identidad.id_peticion
                and anterior.identidad.id_trabajo != vista.identidad.id_trabajo
            ):
                raise ConflictoFragmentos("Peticion asociada a otro trabajo")
        estado.vistas[vista.identidad.id_trabajo] = vista
        self.unidad.almacen.guardados += 1
        self.unidad.verificar_fallo("guardar")


class UnidadTrabajoMemoria:
    def __init__(self, almacen: AlmacenMemoria) -> None:
        self.almacen = almacen
        self._estado = EstadoMemoria()
        self._activa = False
        self._repositorio = RepositorioMemoria(self)

    @property
    def seguimiento(self) -> RepositorioMemoria:
        self.estado_activo()
        return self._repositorio

    def __enter__(self) -> Self:
        if self._activa:
            raise RuntimeError("Unidad ya activa")
        self._estado = deepcopy(self.almacen.estado)
        self._activa = True
        return self

    def __exit__(
        self,
        tipo_error: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        self.revertir()

    def estado_activo(self) -> EstadoMemoria:
        if not self._activa:
            raise RuntimeError("Unidad inactiva")
        return self._estado

    def verificar_fallo(self, etapa: str) -> None:
        if self.almacen.fallo == etapa:
            raise RuntimeError(f"Fallo en {etapa}")

    def preparar_entrada(
        self, consumidor: str, fragmento: DatosCreacion | DatosResultadoCotizacion
    ) -> bool:
        estado = self.estado_activo()
        clave = (consumidor, fragmento.procedencia.event_id)
        anterior = estado.entradas.get(clave)
        if anterior is not None:
            if anterior != fragmento:
                raise ConflictoMensaje("Mismo mensaje con contenido diferente")
            return False
        estado.entradas[clave] = fragmento
        self.verificar_fallo("inbox")
        return True

    def obtener_metadatos(self, id_trabajo: UUID) -> MetadatosProyeccion | None:
        return self.estado_activo().metadatos.get(id_trabajo)

    def guardar_metadatos(self, id_trabajo: UUID, metadatos: MetadatosProyeccion) -> None:
        self.estado_activo().metadatos[id_trabajo] = metadatos
        self.verificar_fallo("metadatos")

    def confirmar(self) -> None:
        estado = self.estado_activo()
        self.verificar_fallo("confirmar")
        self.almacen.estado = deepcopy(estado)
        self.almacen.confirmaciones += 1
        self._activa = False

    def revertir(self) -> None:
        self._estado = EstadoMemoria()
        self._activa = False
