# Contratos de consumo V1

Estado: **schemas provisionales de Seguimiento**, derivados del [contrato común](../plans/comun/01-contratos-y-datos.md). No son exportaciones verificadas de los productores propietarios. El cotejo con Orquestación/Cotizaciones y el intercambio grupal quedan pendientes.

| Evento | Propietario | Schema | Ejemplo |
|---|---|---|---|
| TrabajoCreado.v1 | Orquestación | [trabajo-creado-v1.avsc](trabajo-creado-v1.avsc) | [JSON](trabajo-creado-v1.ejemplo.json) |
| CotizacionRegistrada.v1 | Cotizaciones | [cotizacion-registrada-v1.avsc](cotizacion-registrada-v1.avsc) | [JSON](cotizacion-registrada-v1.ejemplo.json) |
| CotizacionRechazada.v1 | Cotizaciones | [cotizacion-rechazada-v1.avsc](cotizacion-rechazada-v1.avsc) | [JSON](cotizacion-rechazada-v1.ejemplo.json) |

Los registros son planos, sin namespace Avro adicional, con nombres completos `TrabajoCreadoV1`, `CotizacionRegistradaV1` y `CotizacionRechazadaV1`. Todos sus campos son requeridos; las diferencias entre propuesta y rechazo se expresan con registros separados. `importe_menor` es `long` y los ejemplos usan enteros de unidades menores COP. Envelope, campos y semántica siguen el contrato común; orden de campos y schemas concretos son la materialización provisional local.

Las clases lectoras están en `modulos/seguimiento/infraestructura/esquemas/v1/eventos.py`; las pruebas cotejan su schema completo con estos archivos y ejercitan Avro binario. La preparación registra estos schemas y crea suscripciones antes del tráfico. Usar tópicos aislados mientras no exista acuerdo sobre las exportaciones de los propietarios.

El mapeador valida tipo/tópico, clave, UUID, fechas, correlación y tipos; el dominio valida las invariantes del fragmento. Los resultados no publican un campo `estado`: Seguimiento lo deriva del tipo de evento. El formato JSONB privado con `version_formato` no es un contrato Pulsar.

[procedencia.json](procedencia.json) registra el documento fuente y los hashes de los artefactos locales. Las pruebas usan publicadores de contrato expresamente identificados como dobles. No se incluyeron tareas de evolución ni congelación de lectores.
