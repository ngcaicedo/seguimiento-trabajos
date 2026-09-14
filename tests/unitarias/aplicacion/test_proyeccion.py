from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from seguimiento_trabajos.config.bootstrap import componer_seguimiento
from seguimiento_trabajos.modulos.seguimiento.aplicacion.excepciones import ConflictoMensaje
from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import ConflictoFragmentos
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
    TipoRed,
)
from tests.unitarias.aplicacion.dobles.unidad_trabajo import AlmacenMemoria, RelojFijo
from tests.unitarias.dominio.datos import creacion, propuesta, rechazo

INSTANTE = datetime(2026, 9, 14, tzinfo=UTC)


class Escenario:
    def __init__(self) -> None:
        self.almacen = AlmacenMemoria()
        self.reloj = RelojFijo(INSTANTE)
        self.flujo = componer_seguimiento(self.almacen.crear_unidad, self.reloj)

    def recibir(self, fragmento: DatosCreacion | DatosResultadoCotizacion) -> None:
        if isinstance(fragmento, DatosCreacion):
            self.flujo.proyectar_creacion(fragmento)
        else:
            self.flujo.proyectar_resultado(fragmento)


@pytest.mark.parametrize("fragmento", [creacion(), propuesta(), rechazo()])
def test_fragmento_confirmado_visible_desde_otra_unidad(
    fragmento: DatosCreacion | DatosResultadoCotizacion,
) -> None:
    escenario = Escenario()
    assert not escenario.almacen.unidades
    escenario.recibir(fragmento)
    with escenario.almacen.crear_unidad() as unidad:
        vista = unidad.seguimiento.obtener(fragmento.identidad.id_trabajo)
        assert vista is not None
        assert (
            vista.creacion if isinstance(fragmento, DatosCreacion) else vista.resultado
        ) == fragmento
        assert unidad.obtener_metadatos(fragmento.identidad.id_trabajo) is not None
    assert len(escenario.almacen.estado.entradas) == 1
    assert escenario.almacen.unidades[0] is not escenario.almacen.unidades[1]


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
@pytest.mark.parametrize("resultado_primero", [False, True])
def test_ordenes_y_duplicados_conservan_fragmentos_y_fechas(
    resultado: DatosResultadoCotizacion, resultado_primero: bool
) -> None:
    escenario = Escenario()
    fragmentos: list[DatosCreacion | DatosResultadoCotizacion] = (
        [resultado, creacion()] if resultado_primero else [creacion(), resultado]
    )
    for indice, fragmento in enumerate(fragmentos):
        escenario.reloj.instante = INSTANTE + timedelta(minutes=indice)
        escenario.recibir(fragmento)
        escenario.recibir(fragmento)
        equivalente = replace(
            fragmento,
            procedencia=replace(fragmento.procedencia, event_id=UUID(int=1000 + indice)),
        )
        escenario.recibir(equivalente)
    escenario.reloj.instante = INSTANTE + timedelta(days=1)
    for fragmento in fragmentos:
        escenario.recibir(fragmento)
    vista = escenario.almacen.estado.vistas[UUID(int=1)]
    assert vista.creacion == creacion() and vista.resultado == resultado
    assert vista.estado == resultado.estado and vista.creacion_recibida
    assert len(escenario.almacen.estado.entradas) == 4
    assert escenario.almacen.guardados == 2
    assert escenario.almacen.confirmaciones == 4
    assert escenario.reloj.llamadas == 2
    metadatos = escenario.almacen.estado.metadatos[UUID(int=1)]
    assert metadatos.primera_recepcion_en == INSTANTE
    assert metadatos.proyectada_en == INSTANTE + timedelta(minutes=1)


@pytest.mark.parametrize("campo", ["importe", "instante", "causacion", "revision"])
def test_inbox_recuerda_contenido_del_id_equivalente(campo: str) -> None:
    escenario = Escenario()
    original = propuesta()
    equivalente = replace(
        original, procedencia=replace(original.procedencia, event_id=UUID(int=99))
    )
    escenario.recibir(original)
    escenario.recibir(equivalente)
    if campo == "importe":
        alterado = replace(equivalente, importe_menor=10)
    elif campo == "instante":
        alterado = replace(
            equivalente,
            procedencia=replace(equivalente.procedencia, instante=INSTANTE),
        )
    elif campo == "causacion":
        alterado = replace(
            equivalente, procedencia=replace(equivalente.procedencia, causacion=UUID(int=999))
        )
    else:
        alterado = replace(
            equivalente, procedencia=replace(equivalente.procedencia, version_contrato=2)
        )
    anterior = deepcopy(escenario.almacen.estado)
    with pytest.raises(ConflictoMensaje):
        escenario.recibir(alterado)
    assert escenario.almacen.estado == anterior


@pytest.mark.parametrize("cambiar_tipo", [False, True])
def test_id_reutilizado_entre_trabajos_o_tipos_falla(cambiar_tipo: bool) -> None:
    escenario = Escenario()
    original = creacion()
    escenario.recibir(original)
    fragmento = propuesta() if cambiar_tipo else original
    alterado = replace(
        fragmento,
        identidad=replace(fragmento.identidad, id_trabajo=UUID(int=500), id_peticion=UUID(int=501)),
        procedencia=replace(fragmento.procedencia, event_id=original.procedencia.event_id),
    )
    anterior = deepcopy(escenario.almacen.estado)
    with pytest.raises(ConflictoMensaje):
        escenario.recibir(alterado)
    assert escenario.almacen.estado == anterior


@pytest.mark.parametrize("completa", [False, True])
@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
def test_peticion_no_puede_pertenecer_a_otro_trabajo(
    completa: bool, resultado: DatosResultadoCotizacion
) -> None:
    escenario = Escenario()
    escenario.recibir(resultado)
    if completa:
        escenario.recibir(creacion())
    anterior = deepcopy(escenario.almacen.estado)
    alterado = replace(
        resultado,
        identidad=replace(resultado.identidad, id_trabajo=UUID(int=500)),
        procedencia=replace(resultado.procedencia, event_id=UUID(int=501)),
    )
    with pytest.raises(ConflictoFragmentos):
        escenario.recibir(alterado)
    assert escenario.almacen.estado == anterior


@pytest.mark.parametrize("etapa", ["inbox", "guardar", "metadatos", "confirmar"])
@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
@pytest.mark.parametrize("existente", [False, True])
def test_fallo_y_reintento_no_filtran_efectos(
    etapa: str, resultado: DatosResultadoCotizacion, existente: bool
) -> None:
    escenario = Escenario()
    if existente:
        escenario.recibir(creacion())
    anterior = deepcopy(escenario.almacen.estado)
    escenario.reloj.instante += timedelta(hours=1)
    escenario.almacen.fallo = etapa
    with pytest.raises(RuntimeError, match=etapa):
        escenario.recibir(resultado)
    assert escenario.almacen.estado == anterior
    escenario.almacen.fallo = None
    escenario.recibir(resultado)
    escenario.recibir(resultado)
    assert len(escenario.almacen.estado.entradas) == (2 if existente else 1)
    assert escenario.almacen.estado.vistas[UUID(int=1)].resultado == resultado


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
@pytest.mark.parametrize("resultado_primero", [False, True])
@pytest.mark.parametrize("campo", ["id_solicitud", "id_partner", "id_peticion"])
def test_conflictos_identidad_revierten_inbox(
    resultado: DatosResultadoCotizacion, resultado_primero: bool, campo: str
) -> None:
    escenario = Escenario()
    nueva_identidad = replace(resultado.identidad, **{campo: UUID(int=500)})
    procedencia = resultado.procedencia
    if campo == "id_solicitud":
        procedencia = replace(procedencia, correlacion=nueva_identidad.id_solicitud)
    alterado = replace(resultado, identidad=nueva_identidad, procedencia=procedencia)
    primero, segundo = (alterado, creacion()) if resultado_primero else (creacion(), alterado)
    escenario.recibir(primero)
    anterior = deepcopy(escenario.almacen.estado)
    with pytest.raises(ConflictoFragmentos):
        escenario.recibir(segundo)
    assert escenario.almacen.estado == anterior


@pytest.mark.parametrize("campo", ["categoria", "red", "opuestos", "contenido"])
@pytest.mark.parametrize("inverso", [False, True])
def test_conflictos_de_hechos_preservan_estado(campo: str, inverso: bool) -> None:
    escenario = Escenario()
    primero: DatosCreacion | DatosResultadoCotizacion = creacion()
    segundo = propuesta()
    if campo == "categoria":
        segundo = replace(segundo, categoria="OTRA")
    elif campo == "red":
        segundo = replace(segundo, tipo_red=TipoRed.HOMOLOGADA_PARTNER)
    elif campo == "opuestos":
        primero = rechazo()
    else:
        primero = segundo
        segundo = replace(
            segundo,
            importe_menor=10,
            procedencia=replace(segundo.procedencia, event_id=UUID(int=500)),
        )
    fragmentos = [segundo, primero] if inverso else [primero, segundo]
    escenario.recibir(fragmentos[0])
    anterior = deepcopy(escenario.almacen.estado)
    with pytest.raises(ConflictoFragmentos):
        escenario.recibir(fragmentos[1])
    assert escenario.almacen.estado == anterior


def test_revision_compatible_y_zona_horaria_normalizadas() -> None:
    escenario = Escenario()
    original = propuesta()
    escenario.recibir(original)
    equivalente = replace(
        original,
        procedencia=replace(original.procedencia, event_id=UUID(int=500), version_contrato=2),
    )
    escenario.recibir(equivalente)
    escenario.recibir(
        replace(
            equivalente,
            procedencia=replace(
                equivalente.procedencia,
                instante=equivalente.procedencia.instante.astimezone(timezone(timedelta(hours=-5))),
            ),
        )
    )
    assert len(escenario.almacen.estado.entradas) == 2
    assert escenario.almacen.estado.vistas[UUID(int=1)].resultado == original
