# Contratos de Seguimiento

## Contratos conservados E4/E3

Se conservan los artefactos y lectores existentes de `TrabajoCreado.v1`,
`CotizacionRegistrada.v1` y `CotizacionRechazada.v1`. El schema de Trabajo usa
`orquestacion.eventos`; los schemas de cotización siguen sus archivos publicados.
El lector v2 acepta `duracion_estimada_minutos` opcional y mantiene lectura del escritor anterior.
La procedencia histórica consta en `procedencia.json`; E5 no modifica esos artefactos.

## Contratos E5

Fuente funcional: acuerdo `entrega5/contratos-saga-bff-propuesta.md`, confirmado vigente
por el responsable del proyecto. Los detalles Avro se materializan aquí para compartir
los mismos artefactos con el equipo; esto no acredita implementación de los otros servicios.

| Contrato | Dirección | Artefactos |
|---|---|---|
| AbrirSeguimientoTrabajo.v1 | Orquestación → Seguimiento | `abrir-seguimiento-trabajo-v1.avsc`, `.ejemplo.json` |
| CancelarSeguimientoTrabajo.v1 | Orquestación → Seguimiento | `cancelar-seguimiento-trabajo-v1.avsc`, `.ejemplo.json` |
| TrabajoCancelado.v1 | Orquestación → Seguimiento | `trabajo-cancelado-v1.avsc`, `.ejemplo.json` |
| SeguimientoTrabajoAbierto.v1 | Seguimiento → Orquestación | `seguimiento-trabajo-abierto-v1.avsc`, `.ejemplo.json` |
| AperturaSeguimientoFallida.v1 | Seguimiento → Orquestación | `apertura-seguimiento-fallida-v1.avsc`, `.ejemplo.json` |
| SeguimientoTrabajoCancelado.v1 | Seguimiento → Orquestación | `seguimiento-trabajo-cancelado-v1.avsc`, `.ejemplo.json` |

Cada tópico predeterminado es `persistent://public/default/<nombre-del-archivo-sin-extension>`.
La clave es `id_trabajo`. Namespace de entradas: `orquestacion.eventos`, conservando la
convención de sus comandos actuales; namespace de respuestas: `seguimiento.eventos`.

Los registros son planos. UUID y fechas se codifican como strings; fechas con zona horaria
se normalizan a UTC. `version_contrato=1`, `correlacion=id_solicitud` y `id_saga` conserva
su identidad independiente. En respuestas `causacion` identifica el comando recibido.
`id_seguimiento` es nullable en `SeguimientoTrabajoCancelado.v1`; no se añade `id_cotizacion`
a respuestas que no lo contemplan. `version_trabajo` es un entero positivo.

Se valida schema, tipo, tópico, clave, fechas, identidades y correlación antes del handler.
Las reglas de apertura y cancelación pertenecen al dominio. `detalle` nunca dirige transiciones.
Los códigos propios de fallo son `FALLO_CONTROLADO_APERTURA`, `SEGUIMIENTO_CANCELADO`
y `TRABAJO_CANCELADO`. No se añaden campos de prueba al contrato.

Los archivos se cotejan con las clases en `infraestructura/esquemas/v1/saga.py` y se ejercitan
con Avro binario y Pulsar real. Los productores de las pruebas sustituyen explícitamente a
Orquestación. Los hashes E5 y fuente se registran en `procedencia-e5.json`.
