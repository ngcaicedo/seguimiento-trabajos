# Plan de construcción — Seguimiento de Trabajos

Estado: planes 01–04 implementados; 05 implementado y verificado localmente con productores de contrato, integración grupal pendiente; 06 implementado y verificado localmente; planes 07–08 pendientes. Sustitución aprobada por Nicolás el 2026-09-13. Responsable del incremento 01: Nicolás. Repositorio: `entrega4/seguimiento-trabajos`; paquete `seguimiento_trabajos`; módulo `seguimiento`.

## Responsabilidad

Proyectar TrabajoCreado de Orquestación y resultados de Cotizaciones en una base privada consultable. Una petición inicial activa todo el recorrido, sin simular ejecución ni solicitar cierres manualmente. Es un servicio de consulta desplegable, no otro dominio empresarial ni el dueño del Trabajo. No importa paquetes ni consulta bases de los productores.

## Modelo y convergencia

Vista por id_trabajo con id_solicitud, id_partner, id_peticion, fragmento de creación, fragmento de resultado y estado de proyección. Los datos completos y las identidades están en el [contrato común](comun/01-contratos-y-datos.md).

| Hechos recibidos | Estado de la vista | Completitud |
|---|---|---|
| Creación | PENDIENTE_COTIZACION | creacion_recibida=true |
| Propuesta, con o sin creación | COTIZACION_REGISTRADA | true/false según creación |
| Rechazo, con o sin creación | COTIZACION_RECHAZADA | true/false según creación |

Los resultados no confirman que Orquestación ya haya actualizado su Trabajo. Creación tardía completa su fragmento sin retroceder el resultado. IDs inconsistentes o dos resultados opuestos son conflicto; no se decide por timestamp o versión global. La POC admite una petición por trabajo, sin recotización.

Persistir vista/fragmentos/inbox en la misma transacción, bloqueando por trabajo para evitar carreras. Duplicados de mensaje y de hecho tienen control propio. Un mensaje parcial confirmado queda recuperable; si falta creación indefinidamente, se reporta pendiente de proyección y no se fabrican datos.

## E3 reformulado

Evolución futura, fuera del alcance aprobado de la POC V1 del plan 06. Requiere retomar y ajustar el plan 07 antes de implementarse.

Cotizaciones añade duracion_estimada_minutos opcional a CotizacionRegistrada; Seguimiento v2 muestra el dato y filtra ofertas por duración máxima. Null significa desconocido. No es scoring, SLA ni duración observada. Orquestación y cinco lectores antiguos de prueba siguen sin cambios. El informe identifica el reemplazo de la ficha original y los límites académicos.

## Secuencia

| Plan | Resultado | Dependencia |
|---|---|---|
| [01](01-base-tecnologica.md) | Implementado: base tecnológica y pruebas aisladas | Ninguna |
| [02](02-modelo-vista-seedwork.md) | Implementado: vista de seguimiento y reglas de combinación | 01 |
| [03](03-casos-uso-idempotencia.md) | Implementado: proyección e idempotencia con dobles | 02 |
| [04](04-postgresql-vista-inbox.md) | Implementado: PostgreSQL, fragmentos, metadatos e inbox; concurrencia y reinicio | 03 |
| [05](05-pulsar-lectores-v1.md) | Implementado localmente: consumidores V1, seedwork, health y recuperación; integración grupal pendiente | 04; contratos reales de Orquestación y Cotizaciones |
| [06](06-consultas-lector-v2.md) | Implementado: POC V1, GET de seguimiento por ID | 05 |
| [07](07-evolucion-contratos-e3.md) | E3 reformulado: duración estimada de cotización | 06; escritor v2 de Cotizaciones |
| [08](08-despliegue-sustentacion.md) | Despliegue y sustentación | 07 |

## Arranque y despliegue

Una instancia contiene un único proceso FastAPI: API y consumo de Pulsar administrados por lifespan; no publica mensajes ni necesita outbox. Se detiene, reinicia y escala el servicio completo. Los planes 01, 05 y 08 concretan la [base común](comun/02-base-de-implementacion.md) y el [protocolo de plataforma](comun/03-integracion-experimentos-y-entrega.md).

[Evidencia local del plan 01](../evidencias/01-base-tecnologica.md). La composición de 05 ya consume Pulsar en modo operativo; 01 se conserva como evidencia histórica de la base técnica.

[Evidencia local del plan 04](../evidencias/04-postgresql-vista-inbox.md): persistencia y recuperación SQL verificadas; el transporte local de 05 tiene [evidencia propia](../evidencias/05-pulsar-lectores-v1.md); el GET por ID de 06 tiene [evidencia de consulta propia](../evidencias/06-consultas-v1.md).
