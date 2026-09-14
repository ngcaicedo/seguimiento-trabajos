# 05 — Consumidores reales y lectores V1

Estado: implementado y verificado localmente para V1; integración grupal pendiente. Ver [evidencia](../evidencias/05-pulsar-lectores-v1.md). Incorpora los seis ajustes de la [auditoría](auditoria-05-pulsar-lectores-v1.md). Servicio: seguimiento. Ver [modelo y secuencia](README.md), [base común](comun/02-base-de-implementacion.md) y [contratos](comun/01-contratos-y-datos.md).

## Objetivo y alcance

Consumir `TrabajoCreado.v1`, `CotizacionRegistrada.v1` y `CotizacionRechazada.v1` mediante Pulsar, persistir su combinación en PostgreSQL y confirmar cada mensaje después del efecto confirmado. Los tres consumidores se ejecutan como hilos administrados dentro del mismo proceso FastAPI y avanzan aunque no haya solicitudes HTTP.

Este incremento se concentra en V1: fixtures y pruebas contractuales usan revisión 1. Conserva las validaciones del modelo existente; no las endurece ni añade soporte para otras revisiones. No incluye preparación de E3, congelación de lectores, V2, duración estimada ni pruebas de evolución. Este recorte prevalece sobre las referencias a esas tareas en documentos comunes para el cierre de 05.

Seguimiento mantiene una proyección propia de hechos externos. No decide el estado autoritativo del Trabajo, no consulta bases o APIs de los productores y no publica mensajes. No requiere Saga, outbox, bus interno, comandos envoltorio ni otro modelo SQL de Trabajo.

Las consultas empresariales siguen en [06](06-consultas-lector-v2.md). Aquí se verifica la vista mediante el repositorio desde una sesión nueva; HTTP se utiliza para liveness y readiness.

## Dependencias y niveles de cierre

- Local: [04](04-postgresql-vista-inbox.md), con handlers, UoW, inbox, metadatos y concurrencia SQL existentes.
- Contratos: schemas V1 y ejemplos de TrabajoCreado, propiedad de Orquestación, y de ambos resultados, propiedad de Cotizaciones. Registrar origen, revisión y hash de las copias; cotejarlas con los propietarios cuando estén disponibles.
- Infraestructura: PostgreSQL privado de Seguimiento y Pulsar real. Reutilizar el standalone local de Entrada previsto en la base común, sin alterar sus tópicos ni datos.

**Cierre local:** adaptadores y ciclo de vida comprobados con PostgreSQL/Pulsar reales y productores de contrato etiquetados como dobles. Si aún no hay schemas exportados por los propietarios, identificar las copias provisionales derivadas del contrato común y dejar pendiente su cotejo.

**Cierre grupal:** comprobar mensajes emitidos por los productores reales de Orquestación/Cotizaciones y sus efectos persistidos en Seguimiento. Publicar fixtures desde un test no acredita este cierre. La evidencia registra ambos estados por separado; no bloquea el trabajo local por ausencia de productores ni declara integración grupal sin ellos.

## Archivos y responsabilidades

Rutas Python relativas a `src/seguimiento_trabajos/`:

| Archivo o ubicación | Responsabilidad |
|---|---|
| `modulos/seguimiento/infraestructura/consumidores.py` | Procesamiento específico de cada fuente: validación del mensaje, mapeo e invocación del handler; utiliza el consumidor común del seedwork. |
| `modulos/seguimiento/infraestructura/mapeadores_eventos.py` | Validación de la frontera pública y conversión a fragmentos locales. |
| `modulos/seguimiento/infraestructura/esquemas/v1/` | Tres registros lectores Avro conforme a los contratos documentados. |
| `config/bootstrap.py` | Construcción de consumidores y conexión con los casos de uso SQL existentes. |
| `config/procesamiento.py` | Apertura, supervisión y cierre del conjunto de recursos desde lifespan. |
| `seedwork/infraestructura/ciclos.py` | Bucle genérico, señal de parada, hilo y estado de ejecución; sin reglas de eventos. |
| `seedwork/infraestructura/consumidor_pulsar.py` | Mecánica común de apertura, recepción, ACK/NACK y cierre, con procesamiento y clasificación de errores inyectados. |
| `config/rutas.py` | Definición única de tópicos y suscripciones. |
| `config/settings.py`, `config/database.py` | Configuración operativa y límites de E/S compatibles con el cierre. |
| `api/app.py` | Lifespan integrado y health técnico; conserva inyección de dobles. |
| `scripts/preparar_pulsar.py` | Preparación idempotente de tópicos/suscripciones sin mover cursores existentes. |
| `docs/contratos/` | Schemas `.avsc`, ejemplos JSON y procedencia de los contratos V1. |
| `tests/unitarias/`, `tests/contratos/`, `tests/integracion/`, `tests/api/` | Pruebas de frontera, entrega, persistencia y composición. |

Actualizar también `pyproject.toml`, `uv.lock`, `.env.example`, README y `scripts/verify_distribution.py`. Incorporar `pulsar-client[avro]==3.13.0`, tomando broker 4.1.3 como referencia de Entrada. Verificar instalación/importación y documentar versiones reales; no presentarlas como las más recientes.

Mantener `VistaSeguimiento` y `combinar` en dominio; `VistaSeguimientoSQL` en infraestructura/vistas.py. Reutilizar UoW, reintentos, reloj, inbox y serialización genérica del seedwork. SQL y Avro permanecen separados: importar dominio, persistencia o composición SQL no debe cargar Pulsar ni abrir conexiones.

## Seedwork: reutilización y componentes nuevos

Una responsabilidad técnica común pertenece al seedwork aunque tenga un solo módulo consumidor. En 05 se reutilizan las validaciones, reloj, UoW, inbox, serialización y reintentos por colisión ya implementados; no se duplican dentro de los adaptadores nuevos.

Los tres consumidores usan una única implementación de la mecánica Pulsar en `seedwork/infraestructura/consumidor_pulsar.py`, parametrizada con destino, schema lector, función de procesamiento y clasificación de errores. Esta pieza abre/cierra recursos, recibe y ejecuta ACK/NACK conforme al resultado del procesamiento. No conoce TrabajoCreado, CotizacionRegistrada, CotizacionRechazada, los fragmentos de dominio ni sus handlers.

`seedwork/infraestructura/ciclos.py` administra repetición, espera interrumpible, pausa, señal de parada e información de ejecución. No recibe mensajes por su cuenta ni duplica la lógica de ACK. El consumidor ejecuta un paso de transporte; el ciclo administra su repetición. La composición de `config` conecta ambas piezas y administra el presupuesto global de cierre.

El procesamiento específico del módulo valida y traduce el mensaje e invoca el handler. La clasificación de excepciones específicas se conecta desde fuera del seedwork mediante una función inyectada, para que la política común aplique reintento o pausa sin importar el módulo. Un retorno exitoso habilita ACK; una excepción nunca se oculta como éxito. El consumidor no confirma ni revierte SQL: esa responsabilidad permanece en el handler/UoW.

Las esperas de reconexión y reentrega corresponden al transporte/ciclo; los tres intentos transaccionales por colisión permanecen en `seedwork/aplicacion/reintentos.py`. No mezclar ambos mecanismos ni añadir dependencias de Pulsar a aplicación. Los módulos genéricos del seedwork no importan `modulos/seguimiento`, `config` o `api`.

No se necesita una jerarquía de tres subclases de transporte: las diferencias entre fuentes se expresan mediante composición. Schemas, mapeadores, invariantes y metadatos propios de Seguimiento permanecen en el módulo.

## Contratos y traducción

Todos los tópicos usan el prefijo `persistent://public/default/` y clave `id_trabajo`.

| Tópico | Suscripción estable | Traducción y handler |
|---|---|---|
| `trabajo-creado-v1` | `seguimiento-trabajos-v1` | `TrabajoCreado.v1` → `DatosCreacion` → `ProyectarCreacionHandler` |
| `cotizacion-registrada-v1` | `seguimiento-cotizacion-registrada` | `CotizacionRegistrada.v1` → `DatosResultadoCotizacion`, estado `COTIZACION_REGISTRADA` → `ProyectarResultadoHandler` |
| `cotizacion-rechazada-v1` | `seguimiento-cotizacion-rechazada-v1` | `CotizacionRechazada.v1` → `DatosResultadoCotizacion`, estado `COTIZACION_RECHAZADA` → `ProyectarResultadoHandler` |

Fijar nombre completo Avro, tipos, campos requeridos y orden serializado en los schemas. Cotejar registros lectores y ejemplos con esos artefactos; probar codificación/decodificación binaria y consumo real mediante el SDK. La serialización SQL con `version_formato` no es el contrato público.

El mapeador valida correspondencia tópico/tipo, clave del mensaje, UUID, fechas UTC, enumeraciones y correlación con `id_solicitud`. Conserva `event_id`, revisión, instante y causación del productor. Los resultados públicos no contienen el estado local: se deriva del tipo de evento. No inventar oferta para rechazos, nuevas identidades o fechas de ocurrencia. El importe usa Avro `long` y enteros, sin float.

Los handlers reciben los fragmentos directamente y mantienen las invariantes existentes, incluida identidad compartida, categoría/red y unicidad de petición. No duplicar esas reglas en los consumidores ni añadir wrappers de comandos.

Las tres suscripciones comparten el consumidor lógico de inbox existente, `seguimiento.proyeccion`. La deduplicación utiliza el `event_id` del evento, no el MessageId de Pulsar, hilo, réplica o nombre de suscripción. Preservar cada mensaje aceptado, incluso otro ID con contenido equivalente, mediante la UoW actual. El contenido almacenado es el fragmento normalizado, no los bytes originales.

## Entrega, transacción y errores

Secuencia normal: recibir → decodificar/validar → construir fragmento → invocar handler con UoW propia → confirmar efecto → ACK individual. No mantener una transacción SQL abierta durante espera de recepción o ACK. Un duplicado ya confirmado puede terminar sin nuevo commit; recibe ACK tras el retorno exitoso del handler.

| Situación | Tratamiento |
|---|---|
| Timeout sin mensajes | Continuar; no degradar salud por inactividad. |
| Mensaje válido nuevo | Confirmar vista, metadatos e inbox juntos; después ACK individual. |
| Duplicado idéntico | ACK sin repetir efecto ni cambiar fechas. |
| Colisión SQL | Reutilizar los tres intentos con UoW nueva del seedwork. Si se agotan, NACK con demora acotada. |
| Error transitorio de DB | Rollback local, sin ACK; NACK con demora acotada y estado degradado hasta recuperación. |
| Desconexión del broker | Reconectar con espera acotada e interrumpible, conservar nombres de suscripción; recuperar mensajes sin confirmar. Si falla NACK, no asumir que se reprogramó: recuperar mediante reconexión. |
| Datos inválidos, decode inválido o conflicto | Sin ACK ni inbox exitoso; pausar la fuente afectada, conservar diagnóstico y degradar readiness. Las otras fuentes pueden avanzar. |
| Fallo de ACK posterior al commit | Conservar SQL confirmado; reconexión/reentrega deduplicable, sin compensación. |
| Error inesperado de programación | Pausar la fuente y exponer diagnóstico; no convertir cualquier excepción en reintento transitorio infinito. |

El diagnóstico incluye tópico, suscripción, MessageId, motivo y `event_id` cuando pudo decodificarse. Un log de error no exige insertar una marca de éxito en inbox. No copiar literalmente el NACK general y el reintento de todas las excepciones de Entrada.

La pausa no elimina la suscripción ni confirma el mensaje. Para la política simple de la POC, el operador corrige la causa y reinicia el servicio. Con varias réplicas, detener la corrida inválida para evitar que el mensaje rote entre ellas. Los controles negativos usan tópicos aislados. No añadir una plataforma de replay o DLQ como requisito de este incremento.

## Preparación y configuración

Definir configuración `SEGUIMIENTO_*` para URL del broker, DB, modo operativo, tópicos/suscripciones y límites de recepción, conexión y reintento. Conservar un modo técnico explícito para health y pruebas aisladas; el modo operativo requiere configuración completa y no puede quedar silenciosamente sin consumidores. Un modo sin procesamiento no acredita readiness operativa.

Configurar explícitamente `Shared` y posición inicial `Earliest` al crear suscripciones. Preparar las tres antes de publicar tráfico y volver a ejecutar la preparación sin cambiar cursores. Las réplicas de Seguimiento usan los mismos nombres; Orquestación usa suscripciones distintas para recibir su propia copia de los resultados. Nunca renombrar suscripciones, resetear cursores o borrar la base como mecanismo de recuperación.

README debe documentar cómo comprobar/levantar el broker local elegido, preparar recursos, aplicar migraciones y arrancar el único proceso FastAPI. Los scripts resuelven destinos desde la configuración común. Usar namespaces/tópicos aislados para tests y registrar la configuración usada. Las pruebas de integración fallan si falta PostgreSQL o Pulsar; no ocultar indisponibilidad con skips.

## Lifespan, readiness y apagado

Construir/importar la app no abre conexiones. Al entrar en lifespan operativo se crean recursos y se inicia un hilo por fuente. Cada operación obtiene su propia UoW/Session; no compartir una Session entre hilos. Recepción, ACK y SQL síncronos ocurren fuera del event loop. No crear un hilo por mensaje, `BackgroundTasks` por petición ni un ejecutable separado de consumo.

La composición conserva referencias a todos los recursos y limpia también los ya abiertos cuando falla el segundo o tercer consumidor. Distinguir estado iniciando, operativo, recuperando, pausado y detenido, con diagnóstico actual; un hilo vivo o una excepción histórica aislada no determinan salud por sí solos.

- `/health/live` informa vida del proceso y sigue disponible ante errores de procesamiento.
- `/health/ready` responde 200 solo con DB disponible y las tres fuentes operativas; responde 503 en inicio incompleto, recuperación, pausa, procesamiento deshabilitado o cierre. Expone estado por fuente sin secretos. La inactividad normal no es fallo y la recuperación transitoria restablece readiness. El sondeo SQL tiene timeout y no bloquea el event loop.

Al cerrar: marcar no disponible, señalar parada a los tres bucles, impedir nuevas recepciones, terminar o revertir operaciones en curso, cerrar consumidores/clientes y unir hilos; liberar Engine cuando no queden operaciones. No usar `unsubscribe` ni confirmar mensajes solo para apagar.

El presupuesto total de cierre es menor de 10 segundos, compartido por todos los recursos. Usar recepción de hasta 1 segundo y concretar límites de conexión, pool, bloqueo, sentencia SQL y cierre SDK que quepan en ese presupuesto. Documentar y medir los valores elegidos; no copiar los 20 segundos por hilo de Entrada. La parada debe interrumpir las esperas de reintento. Ante corte forzado, el siguiente arranque recupera lo pendiente con la misma DB y suscripciones.

## TDD y matriz de pruebas

Para cada comportamiento no trivial: test rojo, implementación mínima y refactorización. Los tests con dobles comprueban decisiones y orden; PostgreSQL/Pulsar reales y procesos nuevos comprueban durabilidad y recuperación.

| Escenario | Aserciones de cierre |
|---|---|
| Tres contratos V1 | Avro binario → fragmento esperado; IDs, fechas, enteros y procedencia preservados. Rechazar tópico/tipo/clave incoherentes y datos inválidos. |
| Creación → propuesta y creación → rechazo | Una vista completa, dos inbox y metadatos coherentes, consultados desde otra sesión. |
| Propuesta/rechazo antes de creación | Vista parcial persistida; creación tardía completa sin retroceso ni pérdida del resultado. |
| A repetido; B equivalente con otro ID | A no repite efecto; B añade inbox sin cambiar vista/fechas; B alterado se detecta. |
| Identidades o resultados contradictorios | Petición en dos trabajos, IDs cruzados, categoría/red o propuesta/rechazo incompatibles conservan efecto previo; mensaje conflictivo sin ACK. |
| Fallo antes del commit | Ningún efecto parcial o inbox exitoso; reentrega posterior puede confirmar. |
| Corte tras commit antes de ACK | Terminar proceso en ventana controlada, abrir otro con misma DB/suscripción y observar reentrega con un solo efecto. |
| Fallo de ACK | SQL permanece confirmado; recuperación no duplica ni compensa. |
| Error transitorio y mensaje inválido | El transitorio se recupera con espera; el inválido pausa solo su fuente con diagnóstico y readiness 503, sin bucle rápido. |
| Tres tópicos y dos instancias | Tópico vacío no bloquea otros; misma suscripción reparte entregas; carreras preservan fragmentos e inbox. |
| Preparación y fan-out | Preparar dos veces no mueve cursor; tráfico publicado con consumidor detenido se recupera; suscripción separada recibe su propia copia. Identificar si ese receptor es un doble de Orquestación. |
| Lifespan y HTTP | Dos aperturas/cierres sin hilos duplicados o recursos filtrados; consumo sin tráfico HTTP; health concurrente mientras receive espera. |
| Arranque y apagado | Configuración incompleta visible; limpieza ante apertura parcial; parada en receive/transacción/reintento; plazo total medido. |
| Seedwork común | Pruebas con procesamiento falso: retorno exitoso antes de ACK, excepción sin ACK, timeout normal, NACK/reconexión, pausa y cierre. Los tres adaptadores usan la misma mecánica; el seedwork no importa módulos empresariales. |
| Aislamiento y distribución | Dominio/SQL sin Pulsar o red; wheel instalado fuera del árbol fuente incluye los dos componentes nuevos del seedwork y permite composición con dobles. |

Para orden adverso, usar barreras del harness que retrasen TrabajoCreado antes del handler y permitan pasar el resultado. Después liberarlas y observar la combinación. No añadir endpoints empresariales de pausa ni borrar cursores. En recuperación conservar estado entre corte y reinicio; no sustituir reentrega real por llamar dos veces al handler. Las esperas observan etapas concretas con timeout, sin sleeps arbitrarios.

## Verificación y evidencia

Desde la raíz del repositorio, con infraestructura preparada, ejecutar los comandos vigentes:

```bash
uv run --locked pytest tests -q --tb=short
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts migraciones
uv run --locked python scripts/verify_distribution.py
git diff --check
```

Al implementar, añadir al README los comandos exactos y comprobados de preparación, migración, arranque/parada y ejecución del harness. Los adaptadores y scripts locales están implementados; la evidencia distingue pruebas locales de integración grupal pendiente.

Registrar en `docs/evidencias/05-pulsar-lectores-v1.md`: alcance terminado, test rojo significativo, comandos/resultados reales, versiones, origen de schemas, IDs, observación de reentrega, conservación de cursores, salud/cierre y limitaciones. Las pruebas existentes hasta 04 son regresión, no evidencia de transporte Pulsar.

## Criterios de cierre

1. Tres consumidores V1 operativos en el lifespan del único proceso FastAPI, con contratos/mapeadores documentados y sin conexiones al importar.
2. Vista, metadatos e inbox atómicos; ACK posterior al efecto confirmado y duplicados sin segunda mutación.
3. Orden adverso, caída antes/después del commit y recuperación real comprobados con mismos datos y suscripciones.
4. Errores clasificados, pausa y diagnóstico verificables; readiness y apagado dentro del presupuesto medidos.
5. Preparación idempotente, configuración reproducible y mecánica común de consumo/ciclos en seedwork, sin dependencias hacia Seguimiento; aislamiento y distribución comprobados, matriz y checks aprobados.
6. Evidencia distingue cierre local de integración con productores reales. El GET empresarial y cualquier trabajo de evolución no son requisitos de este incremento.

No realizar commit o push salvo solicitud expresa.

## Resultado de ejecución

Consumidor Pulsar, ciclos y reloj de sistema en seedwork; esquemas/mapeadores V1 en el módulo; composición SQL y lifespan integrados. Scripts y comandos operativos documentados en README. La suite incluye broker/PostgreSQL reales, SIGKILL en las dos ventanas transaccionales, HTTP real y SIGTERM. Los contratos son provisionales derivados de los documentos comunes y los publicadores de prueba son dobles. No se implementaron consultas empresariales ni evolución.
