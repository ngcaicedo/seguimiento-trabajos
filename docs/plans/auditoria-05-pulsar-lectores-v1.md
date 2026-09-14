# Auditoría 05 — Consumidores reales y lectores v1

Fecha: 2026-09-13, America/Bogota. Estado: seis recomendaciones incorporadas al plan 05, limitado a V1. Implementación pendiente. Las ubicaciones por línea que siguen corresponden al plan original auditado.

## Dictamen

El [plan 05](05-pulsar-lectores-v1.md) conserva la orientación aprobada, y las seis precisiones de esta auditoría ya se incorporaron a su versión corregida. Las principales son separar el cierre local de la integración grupal, concretar la traducción contractual y convertir las garantías de operación de la base común en pruebas verificables. No recomiendo cambiar la arquitectura.

Las políticas de pausa ante mensajes inválidos, readiness y cierre acotado **ya existen en la base común**. El problema no es su ausencia en el conjunto documental: es que el plan remite a ellas sin precisar cómo sustituir la composición actual ni cómo adaptar una referencia de Entrada cuyo comportamiento difiere de esas políticas.

## Alcance vigente: V1

Por indicación de Nicolás, esta revisión se concentra exclusivamente en el consumo de los tres contratos V1, la persistencia y la recuperación. Se retira la congelación de lectores como hallazgo y como requisito de cierre. No se incluyen preparación de E3, lectores históricos, V2, duración estimada ni pruebas de evolución. Se retiraron los requisitos de E3 de las líneas 13 y 17 del plan original.

Las validaciones existentes del modelo se conservan; este recorte no exige endurecerlas ni añadir soporte para otras revisiones. Los fixtures y la matriz contractual del incremento usan revisión 1.

## Fuentes y decisiones vigentes

Se leyeron los mensajes del usuario y las respuestas finales de las cuatro conversaciones, incluida la página anterior de la segunda. Se contrastaron el código actual de ambos repositorios, los planes locales 01–08, contratos/base común y los planes 05 de Orquestación y Cotizaciones en `entrega4/planes-otros-microservicios`. No se encontró un grafo consultable y no se construyó uno.

| Conversación | Decisión final que debe respetar 05 |
|---|---|
| [Audita plan y muestra diagrama POC](codex://threads/01a09d56-4a1e-7233-8242-0b7fdf3f7103) | Tres fuentes: creación, propuesta y rechazo. Un proceso FastAPI con tres hilos; datos privados; Seguimiento no publica ni decide el estado autoritativo del Trabajo. |
| [Audita el segundo plan](codex://threads/01a09d77-3e18-7940-abc2-ef9fb9eb78f2) | `VistaSeguimiento` en dominio/vistas.py y combinación en dominio/servicios.py; SQL separado. Verificar productores, no solo documentos comunes. |
| [Audita el tercer plan](codex://threads/01a09dcb-455a-72b1-a775-d5bf2fd078ed) | Handlers reciben fragmentos directamente; se eliminaron envoltorios de comandos y validaciones redundantes en handlers. Inbox conserva cada mensaje aceptado; metadatos son locales; rollback es transaccional local. |
| [Audita el cuarto plan](codex://threads/01a09def-c10f-7c13-bea2-589d962e0e4b) | UoW, reintentos y utilidades genéricas pertenecen al seedwork aun con una especialización. `VistaSeguimientoSQL` permanece en infraestructura/vistas.py. |

Referencias de Git al auditar: Seguimiento `6e5693f`; Entrada `57975d2`. Se inspeccionó el árbol de trabajo, no solo esos commits. El plan 05 y otros documentos ya figuraban sin seguimiento en Git antes de esta auditoría.

## 1. P1 — Separar cierre local, API de 06 e integración grupal

**Ubicación:** plan 05, líneas 5 y 15–17.

La secuencia `productores reales → vista persistida → GET posterior` exige una API empresarial que [06](06-consultas-lector-v2.md) implementará después de 05. Hoy [api/app.py](../../src/seguimiento_trabajos/api/app.py) solo expone `/health/live`. Tomar el GET como requisito de cierre local crea una dependencia circular o adelanta funcionalidad sin declararlo.

Además, el índice reconoce contratos reales de Orquestación/Cotizaciones como dependencia, pero la línea de dependencias de 05 solo enumera 04. Los contratos comunes todavía se describen como diseñados, pendientes de exportación y prueba por sus propietarios. Tener sus planes no acredita tener sus productores ejecutables.

**Recomendación:** cerrar el adaptador local con PostgreSQL/Pulsar reales y productores de contrato explícitamente etiquetados, verificando la vista mediante el repositorio desde una sesión nueva. Probar HTTP concurrente con health. Reservar GET empresarial para 06 y registrar por separado el intercambio con productores reales cuando estén disponibles. Esto coincide con la distinción de cierre local/grupal del plan 05 de Orquestación.

**Criterio:** evidencia con dos estados independientes: «adaptador local comprobado» e «integración con productores propietarios comprobada/pendiente». No llamar integración grupal a publicar fixtures desde el propio test.

## 2. P1 — Fijar contratos, mapeo e identidad antes de consumir

**Ubicación:** plan 05, líneas 9, 11 y 13; [contratos comunes](comun/01-contratos-y-datos.md), secciones 2–6.

Los tipos de dominio ya existen, pero falta especificar la frontera de transporte. El esquema SQL de fragmentos tiene `version_formato` y estructura anidada; no es el esquema público Avro. Los resultados públicos no incluyen el campo local `estado`: el mapeador debe derivarlo del tipo de evento. Tampoco debe aceptar un tipo de evento en el tópico de otro solo porque su estructura pueda decodificarse.

**Recomendación:** entregar tres schemas `.avsc`, ejemplos, procedencia/versión del productor y pruebas binarias. Acordar nombre completo Avro, campos requeridos, tipos y orden serializado; comprobar que las clases lectoras representan esos artefactos. Mantener los módulos de esquemas y `mapeadores_eventos.py` separados de la serialización SQL existente.

| Entrada pública | Traducción local |
|---|---|
| `TrabajoCreado.v1` | `DatosCreacion` → `ProyectarCreacionHandler` |
| `CotizacionRegistrada.v1` | `DatosResultadoCotizacion`, estado `COTIZACION_REGISTRADA` → `ProyectarResultadoHandler` |
| `CotizacionRechazada.v1` | `DatosResultadoCotizacion`, estado `COTIZACION_RECHAZADA` → el mismo handler de resultados |

El mapeador conserva `event_id`, revisión, instante, correlación y causación; convierte UUID, fechas UTC y enumeraciones. Valida tópico/tipo y clave `id_trabajo` conforme al contrato; respeta `correlacion == id_solicitud`. No inventa datos de oferta en rechazos, fechas de ocurrencia ni identidades nuevas. El importe usa Avro `long`, sin conversión a float. La verificación de este incremento utiliza revisión 1 en los tres contratos y conserva las validaciones existentes.

**Identidad importante:** las tres suscripciones de transporte no son tres namespaces de inbox. [proyectar_fragmento.py](../../src/seguimiento_trabajos/modulos/seguimiento/aplicacion/handlers/proyectar_fragmento.py) usa `seguimiento.proyeccion` y [la UoW SQL](../../src/seguimiento_trabajos/modulos/seguimiento/infraestructura/unidad_trabajo.py) deduplica por `event_id` del evento. Mantener esa identidad, independiente de réplica, nombre de hilo y MessageId de Pulsar. Cambiarla en 05 debilitaría el reconocimiento de mensajes ya procesados.

**Pruebas:** contrato binario → fragmento esperado; tópico/tipo equivocado; UUID/fecha/dinero inválidos; A repetido idéntico; B equivalente con otro ID; B alterado; misma petición en trabajos distintos. Para V1, «contenido conservado» significa los campos del contrato normalizados; no afirmar que el inbox almacena bytes originales.

## 3. P1 — Clasificar errores y definir qué ocurre con el mensaje recibido

**Ubicación:** plan 05, líneas 11 y 15; base común, «Errores sin plataforma de replay».

«Sin ACK ante error» no basta para especificar recuperación. La referencia [ConsumidorProyeccion de Entrada](../../../entrada-solicitudes-partner/src/solicitudes_partner/modulos/solicitudes/infraestructura/consumidor_proyeccion.py) aplica NACK a cualquier excepción, y su [bucle](../../../entrada-solicitudes-partner/src/solicitudes_partner/seedwork/infraestructura/ciclos.py) continúa reintentando. Copiar ambas piezas no implementaría la pausa por mensaje inválido acordada para esta POC.

| Situación | Comportamiento exigible en 05 |
|---|---|
| Timeout de recepción sin mensajes | Continuar; no degradar readiness por inactividad. |
| Mensaje nuevo válido | Handler confirma vista, metadatos e inbox; luego ACK individual. |
| Duplicado confirmado idéntico | Retorno exitoso del handler y ACK; no exigir un nuevo commit sin cambios. |
| Colisión SQL | Conservar los tres intentos con UoW nueva del seedwork; agotados, reprogramar la entrega con espera acotada. |
| Error transitorio de DB/broker | Sin ACK de trabajo no confirmado; elegir NACK con demora o reconexión/reentrega explícita. No retener el mensaje indefinidamente mientras se reciben otros. |
| Datos inválidos/conflicto | Sin ACK, sin insertar inbox exitoso; pausar la fuente afectada, conservar diagnóstico y degradar readiness. Las otras fuentes pueden seguir. |
| Fallo de ACK después del commit | No compensar SQL. La eventual reentrega debe reconocer el efecto confirmado. |
| Error inesperado de programación | Visible en supervisión; no clasificar automáticamente todo `Exception` como transitorio. |

Para errores de decodificación, `event_id` puede no estar disponible: registrar al menos tópico, suscripción, MessageId y motivo. No añadir un inbox de éxito para poder registrar el error. La pausa no equivale a eliminar la suscripción ni a confirmar el mensaje. Con réplicas Shared, se mantiene el límite ya documentado de detener la corrida inválida para evitar rotación entre instancias.

**Pruebas:** fallo antes de commit, después de commit/antes de ACK, fallo de ACK, conflicto, decode inválido y recuperación transitoria. Verificar estado persistido, número de ACK, diagnóstico y ausencia de reintento rápido de mensajes inválidos.

## 4. P1 — Concretar composición, supervisión y cierre con presupuesto total

**Ubicación:** plan 05, líneas 9, 11 y 19; base común, «Ciclo de vida integrado».

La app actual utiliza `sin_procesamiento` por defecto. [Settings](../../src/seguimiento_trabajos/config/settings.py) no tiene configuración Pulsar ni modos operativos; la [base de datos](../../src/seguimiento_trabajos/config/database.py) no fija límites de conexión, pool, espera de bloqueo o sentencia para el presupuesto de apagado. Iniciar tres hilos no resuelve por sí solo estas dependencias.

En Entrada, `Procesamiento.detener(timeout=20)` concede hasta 20 segundos por hilo y `errores` guarda la última excepción sin distinguir recuperación. No satisface por copia el cierre total menor de 10 segundos ni un estado de salud actual.

**Recomendación:** `config/procesamiento.py` ensambla tres consumidores y mantiene sus recursos; `seedwork/infraestructura/ciclos.py` posee ciclo, señal de parada y estado genérico. Mapeos/reglas de eventos permanecen en el módulo. Reutilizar la factoría SQL existente y crear una UoW/Session por operación. No reintroducir comandos envoltorio, un segundo ORM de Trabajo, outbox ni bus interno.

Precisar arranque operativo con configuración completa y fallback técnico de health para el uso aislado ya soportado. Una configuración operativa incompleta no debe anunciarse como lista. Construir/importar la app sigue sin abrir conexiones; el lifespan inicia trabajo fuera del event loop, conserva inyección de dobles y limpia recursos ante fallo parcial del segundo o tercer consumidor.

Añadir `/health/ready` técnico en 05: DB, conexión/estado de las tres fuentes y diagnóstico actual. Mantener liveness separado. Definir recuperación de readiness tras errores transitorios y estado detenido ante mensajes inválidos; no basta consultar si un hilo está vivo.

El cierre debe señalar parada a los tres bucles, impedir nuevas recepciones, terminar o revertir operaciones en curso, cerrar clientes y unir hilos con un plazo compartido. Ajustar límites reales de SDK/SQL al plazo; liberar Engine después de terminar las operaciones. Nunca usar `unsubscribe` durante cierre ni ACK «por apagar».

**Pruebas:** dos ciclos de lifespan sin duplicación; consumo sin HTTP; health responde durante espera de recepción; fallo parcial de inicio; caída/recuperación de conexión; parada durante receive y transacción; tiempo total de cierre medido. Las barreras pertenecen al harness, no a endpoints empresariales.

## 5. P2 — Hacer reproducible la preparación de infraestructura y cursores

**Ubicación:** plan 05, líneas 9 y 11.

Actualmente [pyproject.toml](../../pyproject.toml) no incluye Pulsar y [Compose](../../docker-compose.yaml) solo contiene PostgreSQL. Es correcto para 04, pero 05 debe enumerar la dependencia Avro, lockfile, variables, broker y script de preparación. Los documentos comunes proponen reutilizar el standalone local de Entrada; no hace falta crear otro broker ni tocar sus tópicos empresariales.

| Tópico, con prefijo `persistent://public/default/` | Suscripción estable de Seguimiento |
|---|---|
| `trabajo-creado-v1` | `seguimiento-trabajos-v1` |
| `cotizacion-registrada-v1` | `seguimiento-cotizacion-registrada` |
| `cotizacion-rechazada-v1` | `seguimiento-cotizacion-rechazada-v1` |

**Recomendación:** añadir `config/rutas.py`, configuración `SEGUIMIENTO_*`, `.env.example`, script idempotente y comandos comprobados contra el entorno elegido. Tomar cliente `pulsar-client[avro]==3.13.0` y broker 4.1.3 como referencia probada en Entrada, no como afirmación de versiones más recientes. No cambiar nombres para cada arranque ni borrar cursores para recuperar.

Declarar `Shared` y posición inicial explícitamente; el cliente 3.13.0 instalado usa por defecto `Exclusive` y `Latest`. La posición inicial sirve para crear una suscripción, no para reiniciar su cursor existente. Preparar y comprobar suscripciones antes del tráfico.

**Pruebas:** preparar dos veces sin mover cursor; publicar antes de arrancar el consumidor, con suscripción preparada; reiniciar con mismo nombre y backlog; réplicas compartiendo nombre y un efecto por evento; copia independiente para Orquestación. Usar tópicos aislados para controles negativos.

## 6. P2 — Definir una matriz de cierre basada en fallos y efectos

**Ubicación:** plan 05, líneas 15–21.

Las pruebas descritas son una buena base, pero requieren aserciones y límites concretos. La cobertura SQL actual no prueba ACK, reentrega o autonomía de los bucles.

| Escenario de 05 | Evidencia que debe observarse |
|---|---|
| Creación → propuesta y creación → rechazo | Una vista completa, dos entradas inbox y metadatos coherentes. |
| Propuesta/rechazo antes de creación | Vista parcial persistida; tras liberar barrera, completa sin retroceso. |
| Reentrega A y hecho equivalente B | Sin segunda mutación por A; B registrado, fechas/vista sin cambios. |
| Fallo antes del commit | Ningún efecto parcial/inbox exitoso; reentrega posterior aplica el efecto. |
| Corte de proceso tras commit y antes de ACK | Proceso nuevo, misma DB/suscripción, reentrega observada, un solo efecto. No limpiar estado entre ambas fases. |
| Conflicto con evento previo | Conserva vista/fechas/inbox previo, sin ACK exitoso del contradictorio; fuente pausada y diagnóstico. |
| Tres tópicos y dos instancias | Un tópico vacío no bloquea los otros; carreras preservan fragmentos y deduplicación SQL. |
| HTTP y cierre | Health concurrente, readiness verificable y plazo global de apagado medido. |
| Contratos de propietarios | Schemas y mensajes interoperables; si se usan dobles, declarar pendiente el recorrido grupal. |

Usar IDs correlacionados, observación de DB desde otra sesión y estados del broker, con esperas acotadas. Un ACK capturado por mock verifica orden de llamadas; un proceso terminado con corte controlado y reentrega real verifica recuperación. No sustituirlo por invocar el handler dos veces ni por sleeps arbitrarios.

Para la implementación futura, identificar en README los comandos de preparación, migración, arranque y pruebas; ejecutar tests, Ruff, formato, mypy y verificación de distribución vigentes. Las pruebas de integración deben fallar si falta infraestructura. Conservar en `docs/evidencias/05-pulsar-lectores-v1.md` versiones, comandos reales, IDs, cursores/recuperación y limitaciones.

## Verificación realizada durante la auditoría inicial

| Comando, desde cada repositorio | Resultado |
|---|---|
| Seguimiento: `uv run --locked pytest tests -q --tb=short` | **242 aprobadas**, incluidas **51 PostgreSQL**. Bases temporales administradas por el fixture existente. |
| Entrada: `uv run --locked pytest tests/unitarias/test_consumidor_proyeccion.py tests/unitarias/test_procesamiento.py tests/api/test_procesamiento.py -q --tb=short` | **7 aprobadas**. Pruebas focalizadas; no suite completa de Entrada. |
| Inspección del SDK instalado | Cliente 3.13.0; defaults de suscripción inspeccionados. Sin tráfico Pulsar. |

Ambas suites emitieron la advertencia ya existente de Starlette/AnyIO. No se ejecutó integración con Orquestación/Cotizaciones ni despliegue. Los 242 tests acreditan la base actual hasta 04; no significan que 05 esté implementado.

Context7 se consultó para Pulsar y se complementó con documentación oficial y código del SDK instalado. Las URLs de API 3.13.x no pudieron abrirse desde el buscador; las afirmaciones específicas de esa versión se basan en la instalación local inspeccionada. No se atribuye a Python comportamiento de ejemplos Java.

## Incorporación al plan

Los seis hallazgos quedaron incorporados en el [plan 05 corregido](05-pulsar-lectores-v1.md):

| Hallazgo | Secciones del plan |
|---|---|
| 1. Cierre local/API/integración | Objetivo y alcance; Dependencias y niveles de cierre. |
| 2. Contratos y mapeo | Archivos y responsabilidades; Contratos y traducción. |
| 3. Errores y ACK | Entrega, transacción y errores. |
| 4. Composición y cierre | Lifespan, readiness y apagado. |
| 5. Preparación | Preparación y configuración. |
| 6. Pruebas y evidencia | TDD y matriz de pruebas; Verificación y evidencia; Criterios de cierre. |

Se conserva el alcance V1 y las decisiones de dominio, seedwork y persistencia. Incorporación documental no significa implementación ni integración comprobada.

Tras la revisión específica del seedwork, se explicitó `seedwork/infraestructura/consumidor_pulsar.py` junto con `ciclos.py`: transporte común y ciclo separados, procesamiento/clasificación inyectados, reutilización de UoW/inbox/reintentos y pruebas de aislamiento. Los esquemas y mapeadores permanecen en el módulo. Esta precisión forma parte de los hallazgos 4 y 6.

Solo cambiaron el plan y esta auditoría. Se verificaron enlaces locales y formato; no se repitieron pruebas de código por este cambio documental. Sin commit ni push.
