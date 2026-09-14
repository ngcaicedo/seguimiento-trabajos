from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest

from seguimiento_trabajos.modulos.seguimiento.dominio.excepciones import (
    ConflictoFragmentos,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.objetos_valor import (
    DatosCreacion,
    DatosResultadoCotizacion,
    EstadoProyeccion,
    MotivoRechazo,
    TipoRed,
)
from seguimiento_trabajos.modulos.seguimiento.dominio.servicios import combinar
from seguimiento_trabajos.modulos.seguimiento.dominio.vistas import VistaSeguimiento
from seguimiento_trabajos.seedwork.dominio.excepciones import DatosInvalidos
from tests.unitarias.dominio.datos import creacion, identidad, propuesta, rechazo


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
def test_ambos_ordenes_convergen_y_duplicados_conservan_fragmentos(
    resultado: DatosResultadoCotizacion,
) -> None:
    origen = creacion()
    primera = combinar(combinar(None, origen), resultado)
    segunda = combinar(combinar(None, resultado), origen)
    assert primera == segunda
    assert primera.creacion_recibida
    assert primera.estado == resultado.estado
    assert primera.creacion is origen
    assert primera.resultado is resultado
    for fragmento in (origen, resultado, origen, resultado):
        assert combinar(primera, fragmento) is primera
    assert replace(primera) == primera


@pytest.mark.parametrize("fragmento", [creacion(), propuesta(), rechazo()])
def test_parciales_y_reconstruccion(fragmento: Any) -> None:
    vista = combinar(None, fragmento)
    assert vista.identidad == identidad()
    assert vista.creacion_recibida == (fragmento == creacion())
    assert vista.estado == fragmento.estado
    assert vista.categoria == (None if fragmento == rechazo() else "PLOMERIA")
    assert vista.tipo_red == (None if fragmento == rechazo() else TipoRed.GENERAL_HDA)
    assert vista.referencia_externa == ("PARTNER-1" if vista.creacion_recibida else None)
    assert vista.creado_en == (creacion().creado_en if vista.creacion_recibida else None)
    assert replace(vista) == vista


@pytest.mark.parametrize("campo", ["id_trabajo", "id_solicitud", "id_partner", "id_peticion"])
def test_identidad_ajena_falla_en_ambos_ordenes(campo: str) -> None:
    original = creacion()
    nueva_identidad = replace(identidad(), **{campo: UUID(int=99)})
    otro = replace(
        propuesta(),
        identidad=nueva_identidad,
        procedencia=replace(propuesta().procedencia, correlacion=nueva_identidad.id_solicitud),
    )
    ordenes: list[
        tuple[DatosCreacion | DatosResultadoCotizacion, DatosCreacion | DatosResultadoCotizacion]
    ] = [(original, otro), (otro, original)]
    for anterior, entrante in ordenes:
        vista = combinar(None, anterior)
        with pytest.raises(ConflictoFragmentos):
            combinar(vista, entrante)
        assert vista == combinar(None, anterior)


@pytest.mark.parametrize(
    "cambio", [{"categoria": "OTRA"}, {"tipo_red": TipoRed.HOMOLOGADA_PARTNER}]
)
def test_categoria_y_red_incompatibles_fallan_incluso_al_reconstruir(
    cambio: dict[str, Any],
) -> None:
    diferente = replace(propuesta(), **cambio)
    with pytest.raises(ConflictoFragmentos):
        VistaSeguimiento(creacion=creacion(), resultado=diferente)
    ordenes: list[
        tuple[DatosCreacion | DatosResultadoCotizacion, DatosCreacion | DatosResultadoCotizacion]
    ] = [(creacion(), diferente), (diferente, creacion())]
    for anterior, entrante in ordenes:
        with pytest.raises(ConflictoFragmentos):
            combinar(combinar(None, anterior), entrante)


@pytest.mark.parametrize("fragmento", [creacion(), propuesta(), rechazo()])
def test_nuevo_id_equivalente_conserva_procedencia_original(fragmento: Any) -> None:
    vista = combinar(None, fragmento)
    nuevo = replace(
        fragmento,
        procedencia=replace(
            fragmento.procedencia,
            event_id=UUID(int=90),
            causacion=UUID(int=91),
            instante=fragmento.procedencia.instante + timedelta(days=1),
        ),
    )
    assert combinar(vista, nuevo) is vista


@pytest.mark.parametrize(
    "cambio",
    [
        {"instante": datetime(2026, 9, 14, tzinfo=UTC)},
        {"causacion": UUID(int=99)},
        {"version_contrato": 2},
    ],
)
def test_mismo_id_con_procedencia_alterada_falla(cambio: dict[str, Any]) -> None:
    original = propuesta()
    with pytest.raises(ConflictoFragmentos):
        combinar(
            combinar(None, original),
            replace(original, procedencia=replace(original.procedencia, **cambio)),
        )


@pytest.mark.parametrize(
    "fragmento,cambio",
    [
        (creacion(), {"referencia_externa": "OTRA"}),
        (creacion(), {"id_politica": UUID(int=99)}),
        (creacion(), {"version_politica": 2}),
        (propuesta(), {"importe_menor": 100}),
        (propuesta(), {"id_proveedor": UUID(int=99)}),
        (propuesta(), {"version_catalogo": 2}),
        (rechazo(), {"motivo": MotivoRechazo.SIN_PROVEEDOR_EN_RED}),
    ],
)
@pytest.mark.parametrize("nuevo_id", [False, True])
def test_hecho_alterado_no_reemplaza_fragmento(
    fragmento: Any, cambio: dict[str, Any], nuevo_id: bool
) -> None:
    diferente = replace(fragmento, **cambio)
    if nuevo_id:
        diferente = replace(
            diferente, procedencia=replace(diferente.procedencia, event_id=UUID(int=90))
        )
    for anterior, entrante in [(fragmento, diferente), (diferente, fragmento)]:
        vista = combinar(None, anterior)
        with pytest.raises(ConflictoFragmentos):
            combinar(vista, entrante)
        assert vista == combinar(None, anterior)


def test_resultados_opuestos_no_reemplazan() -> None:
    for anterior, entrante in [(propuesta(), rechazo()), (rechazo(), propuesta())]:
        with pytest.raises(ConflictoFragmentos):
            combinar(combinar(None, anterior), entrante)


@pytest.mark.parametrize(
    "fragmento,cambio",
    [
        (creacion(), {"referencia_externa": ""}),
        (creacion(), {"categoria": " "}),
        (creacion(), {"tipo_solicitud": "INSTALACION"}),
        (creacion(), {"version_trabajo": 2}),
        (creacion(), {"version_politica": True}),
        (creacion(), {"id_politica": UUID(int=0)}),
        (creacion(), {"creado_en": datetime(2026, 1, 1)}),
        (creacion(), {"estado": EstadoProyeccion.COTIZACION_REGISTRADA}),
        (propuesta(), {"importe_menor": 0}),
        (propuesta(), {"importe_menor": -1}),
        (propuesta(), {"importe_menor": True}),
        (propuesta(), {"importe_menor": 1.5}),
        (propuesta(), {"moneda": "USD"}),
        (propuesta(), {"id_proveedor": None}),
        (propuesta(), {"id_cotizacion": None}),
        (propuesta(), {"categoria": None}),
        (propuesta(), {"tipo_red": "GENERAL_HDA"}),
        (propuesta(), {"motivo": MotivoRechazo.SIN_OFERTA_PARA_CATEGORIA}),
        (rechazo(), {"motivo": None}),
        (rechazo(), {"motivo": "OTRO"}),
        (rechazo(), {"importe_menor": 1}),
        (rechazo(), {"id_cotizacion": UUID(int=90)}),
        (rechazo(), {"categoria": "PLOMERIA"}),
        (rechazo(), {"version_catalogo": 0}),
        (rechazo(), {"version_cotizacion": True}),
        (rechazo(), {"version_cotizacion": 2}),
        (rechazo(), {"estado": EstadoProyeccion.PENDIENTE_COTIZACION}),
    ],
)
def test_datos_invalidos_no_se_construyen(fragmento: Any, cambio: dict[str, Any]) -> None:
    with pytest.raises(DatosInvalidos):
        replace(fragmento, **cambio)


@pytest.mark.parametrize(
    "cambio",
    [
        {"event_id": UUID(int=0)},
        {"version_contrato": True},
        {"version_contrato": 0},
        {"instante": datetime(2026, 1, 1)},
        {"tipo": "Otro.v1"},
    ],
)
def test_procedencia_invalida(cambio: dict[str, Any]) -> None:
    with pytest.raises(DatosInvalidos):
        replace(propuesta().procedencia, **cambio)


def test_tipo_correlacion_y_revision_del_fragmento() -> None:
    with pytest.raises(DatosInvalidos):
        replace(creacion(), procedencia=propuesta().procedencia)
    with pytest.raises(DatosInvalidos):
        replace(creacion(), procedencia=replace(creacion().procedencia, correlacion=UUID(int=99)))
    with pytest.raises(DatosInvalidos):
        replace(creacion(), procedencia=replace(creacion().procedencia, version_contrato=2))


def test_propuesta_revision_compatible_no_exige_duracion() -> None:
    original = propuesta()
    evolucionada = replace(
        original,
        procedencia=replace(original.procedencia, event_id=UUID(int=90), version_contrato=2),
    )
    assert combinar(None, evolucionada).resultado is evolucionada
    assert combinar(combinar(None, original), evolucionada).resultado is original


def test_normalizacion_utc_no_cambia_hecho() -> None:
    original = creacion()
    zona = timezone(timedelta(hours=-5))
    equivalente = replace(
        original,
        creado_en=original.creado_en.astimezone(zona),
        procedencia=replace(
            original.procedencia, instante=original.procedencia.instante.astimezone(zona)
        ),
    )
    assert equivalente.creado_en.tzinfo is UTC
    assert equivalente.procedencia.instante.tzinfo is UTC
    vista = combinar(None, original)
    assert combinar(vista, equivalente) is vista


def test_vista_vacia_tipos_ajenos_e_identidad_invalida() -> None:
    with pytest.raises(DatosInvalidos):
        VistaSeguimiento()
    with pytest.raises(DatosInvalidos):
        VistaSeguimiento(creacion=cast_invalido())
    with pytest.raises(DatosInvalidos):
        replace(identidad(), id_partner=UUID(int=0))


def cast_invalido() -> Any:
    return {"creacion": "invalida"}


def test_inmutabilidad_anidada_y_estado_derivado() -> None:
    vista = combinar(None, creacion())
    for objeto, campo, valor in [
        (vista, "estado", EstadoProyeccion.COTIZACION_REGISTRADA),
        (vista, "creacion_recibida", False),
        (vista.creacion, "categoria", "OTRA"),
        (vista.identidad, "id_trabajo", UUID(int=99)),
    ]:
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(objeto, campo, valor)


def test_mismo_event_id_no_identifica_creacion_y_resultado() -> None:
    resultado = replace(
        propuesta(),
        procedencia=replace(propuesta().procedencia, event_id=creacion().procedencia.event_id),
    )
    with pytest.raises(ConflictoFragmentos):
        combinar(combinar(None, creacion()), resultado)


@pytest.mark.parametrize("resultado", [propuesta(), rechazo()])
def test_duplicados_intercalados_y_tiempos_no_eligen_ganador(
    resultado: DatosResultadoCotizacion,
) -> None:
    origen = creacion()
    resultado = replace(
        resultado,
        procedencia=replace(resultado.procedencia, instante=origen.creado_en - timedelta(days=1)),
    )
    ordenes: list[tuple[DatosCreacion | DatosResultadoCotizacion, ...]] = [
        (origen, origen, resultado),
        (resultado, resultado, origen),
    ]
    for orden in ordenes:
        vista = None
        for fragmento in orden:
            vista = combinar(vista, fragmento)
        assert vista == VistaSeguimiento(creacion=origen, resultado=resultado)


def test_red_homologada_coherente_se_combina() -> None:
    origen = replace(creacion(), tipo_red=TipoRed.HOMOLOGADA_PARTNER)
    resultado = replace(propuesta(), tipo_red=TipoRed.HOMOLOGADA_PARTNER)
    assert combinar(combinar(None, resultado), origen).tipo_red is TipoRed.HOMOLOGADA_PARTNER


def test_combinacion_rechaza_tipos_ajenos() -> None:
    with pytest.raises(DatosInvalidos):
        combinar(None, cast_invalido())
    with pytest.raises(DatosInvalidos):
        combinar(cast_invalido(), creacion())
