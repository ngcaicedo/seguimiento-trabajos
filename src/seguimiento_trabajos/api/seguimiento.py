from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from seguimiento_trabajos.config.bootstrap import (
    componer_consulta,
    componer_listado,
    compose_attention,
)
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.consultar_seguimiento import (
    ConsultarSeguimientoHandler,
    GetAttentionHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.handlers.listar_seguimiento import (
    ListarSeguimientoHandler,
)
from seguimiento_trabajos.modulos.seguimiento.aplicacion.vistas import (
    AttentionView,
    RespuestaSeguimiento,
)
from seguimiento_trabajos.seedwork.aplicacion.excepciones import PersistenciaNoDisponible

router = APIRouter(prefix="/seguimiento/trabajos", tags=["seguimiento"])


def obtener_consulta(request: Request) -> ConsultarSeguimientoHandler:
    base = cast(Database | None, request.app.state.database)
    if base is None:
        raise HTTPException(503, "Base de datos no configurada")
    return componer_consulta(base)


@router.get(
    "/{id_trabajo}",
    response_model=RespuestaSeguimiento,
    responses={
        404: {"description": "No disponible en la proyeccion; puede existir retraso"},
        422: {"description": "ID invalido"},
        503: {"description": "Persistencia no disponible"},
    },
)
def consultar_seguimiento(
    id_trabajo: UUID,
    consultar: Annotated[ConsultarSeguimientoHandler, Depends(obtener_consulta)],
) -> RespuestaSeguimiento:
    if id_trabajo.int == 0:
        raise HTTPException(422, "El ID del trabajo debe ser un UUID no nulo")
    try:
        respuesta = consultar(id_trabajo)
    except PersistenciaNoDisponible as error:
        raise HTTPException(503, "Persistencia no disponible") from error
    if respuesta is None:
        raise HTTPException(404, "No disponible en la proyeccion")
    return respuesta


def obtener_listado(request: Request) -> ListarSeguimientoHandler:
    base = cast(Database | None, request.app.state.database)
    if base is None:
        raise HTTPException(503, "Base de datos no configurada")
    return componer_listado(base)


@router.get("", response_model=list[RespuestaSeguimiento])
def listar_seguimiento(
    listar: Annotated[ListarSeguimientoHandler, Depends(obtener_listado)],
    duracion_maxima_minutos: Annotated[int | None, Query(gt=0)] = None,
    limite: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[RespuestaSeguimiento]:
    try:
        return listar(duracion_maxima_minutos, limite)
    except PersistenciaNoDisponible as error:
        raise HTTPException(503, "Persistencia no disponible") from error


def get_attention_query(request: Request) -> GetAttentionHandler:
    database = cast(Database | None, request.app.state.database)
    if database is None:
        raise HTTPException(503, "Base de datos no configurada")
    return compose_attention(database)


@router.get(
    "/{id_trabajo}/atencion",
    response_model=AttentionView,
    responses={
        404: {"description": "Informacion local no disponible"},
        503: {"description": "Persistencia no disponible"},
    },
)
def get_attention(
    id_trabajo: UUID, query: Annotated[GetAttentionHandler, Depends(get_attention_query)]
) -> AttentionView:
    if id_trabajo.int == 0:
        raise HTTPException(422, "El ID del trabajo debe ser un UUID no nulo")
    try:
        result = query(id_trabajo)
    except PersistenciaNoDisponible as error:
        raise HTTPException(503, "Persistencia no disponible") from error
    if result is None:
        raise HTTPException(404, "Informacion local no disponible")
    return result
