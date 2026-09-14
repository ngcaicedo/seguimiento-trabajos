# Seguimiento de Trabajos

Planes 01–05 implementados y verificados localmente: base FastAPI, modelo, persistencia PostgreSQL y tres consumidores Pulsar V1. El cierre grupal con productores propietarios sigue pendiente; los schemas y productores de prueba se identifican en [contratos](docs/contratos/README.md).

El modelo puro combina TrabajoCreado y los resultados de Cotizaciones en una vista inmutable. Los casos de uso coordinan proyección, inbox y metadatos mediante una UoW comprobada con dobles y PostgreSQL real. El modo operativo inicia tres hilos de consumo desde lifespan; las consultas empresariales siguen para 06. El modo técnico predeterminado solo ofrece health y no inicia consumo.

## Instalación y ejecución

Requisitos: uv y Python 3.12. La API de liveness y las pruebas unitarias no necesitan infraestructura. Las migraciones requieren PostgreSQL 17; la suite completa requiere además Pulsar. El entorno local utiliza PostgreSQL 17.6 y broker 4.1.3, con cliente Python 3.13.0.

```bash
uv sync --locked
uv run --locked uvicorn seguimiento_trabajos.api.app:create_app --factory --host 127.0.0.1 --port 8003
```

Desde otra terminal:

```bash
curl --fail --silent --show-error -i http://127.0.0.1:8003/health/live
```

Respuesta esperada: HTTP 200 y `{"status":"ok","service":"seguimiento-trabajos"}`. Detener con Ctrl+C. Liveness acredita que el proceso responde. `/health/ready` devuelve 503 en este modo técnico; no hay API de consultas de trabajos todavía.

## Configuración

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `SEGUIMIENTO_SERVICE_NAME` | `seguimiento-trabajos` | Identidad de liveness. |
| `SEGUIMIENTO_DATABASE_URL` | Vacía | URL de desarrollo para Engine y migración manual. |
| `SEGUIMIENTO_TEST_DATABASE_URL` | PostgreSQL local en 55435 | URL administrativa del fixture, que crea y elimina sus propias bases de prueba. |
| `SEGUIMIENTO_PROCESSING_ENABLED` | `false` | `true` activa consumo y exige DB; otro texto distinto de true/false es inválido. |
| `SEGUIMIENTO_PULSAR_URL` | `pulsar://127.0.0.1:6650` | Broker operativo. |
| `SEGUIMIENTO_TOPICO_CREACION` | `persistent://public/default/trabajo-creado-v1` | TrabajoCreado. |
| `SEGUIMIENTO_TOPICO_REGISTRADA` | `persistent://public/default/cotizacion-registrada-v1` | Propuestas. |
| `SEGUIMIENTO_TOPICO_RECHAZADA` | `persistent://public/default/cotizacion-rechazada-v1` | Rechazos. |
| `SEGUIMIENTO_RECEPCION_MS` | `500` | Recepción entre 1 y 1000 ms. |
| `SEGUIMIENTO_REENTREGA_MS` | `1000` | Demora NACK, mínimo 1000 ms. |
| `SEGUIMIENTO_PAUSA_REINTENTO` | `0.5` | Espera interrumpible entre reintentos; mayor que 0 y hasta 30 s. |
| `SEGUIMIENTO_TEST_PULSAR_URL` | `pulsar://127.0.0.1:6650` | Broker para tópicos aislados de pruebas. |

[.env.example](.env.example) describe las variables. Se leen del entorno del proceso; la aplicación no carga `.env` automáticamente. No usar las variables `PARTNER_*` de Entrada.

## Estructura

```text
src/seguimiento_trabajos/
  api/app.py
  config/settings.py
  config/database.py
  config/bootstrap.py
  modulos/seguimiento/{dominio,aplicacion,infraestructura}/
  seedwork/{dominio,aplicacion,infraestructura}/
tests/{unitarias,api,integracion,contratos}/
scripts/verify_distribution.py
docs/plans/
docs/plans/comun/
docs/evidencias/
docs/referencias/
```

El módulo separa datos y enumeraciones en `dominio/objetos_valor.py`, `VistaSeguimiento` en `dominio/vistas.py` y combinación pura en `dominio/servicios.py`. Seedwork contiene validaciones de UUID, enteros positivos, texto y fechas UTC, y la excepción común DatosInvalidos. Identidad, procedencia, creación y resultado utilizan esas validaciones; las reglas específicas permanecen en el módulo. La factoría recibe configuración, factoría de base y ciclo de procesamiento sustituibles. El ciclo predeterminado respeta el modo técnico u operativo configurado. `config/bootstrap.py` compone los dos handlers con una factoría de UoW y reloj explícitos; ofrece composición con puertos o adaptadores SQL; no abre conexiones ni inicia procesamiento al construirlos. El seedwork incorpora `consumidor_pulsar.py`, `ciclos.py` y `reloj.py`; el módulo aporta schemas, mapeadores y procesamiento específico. No hay bus ni outbox.

## Modelo de seguimiento

`combinar(vista, fragmento)` recibe una vista opcional y datos propios de creación o resultado. Devuelve una vista nueva al incorporar un fragmento; un duplicado equivalente devuelve la vista previa. `VistaSeguimiento` también se reconstruye directamente desde fragmentos validados, sin eventos, reloj ni IDs nuevos. Las identidades se consultan mediante `vista.identidad`.

| Fragmentos recibidos | Estado | Creación recibida |
|---|---|---|
| Creación | PENDIENTE_COTIZACION | Sí |
| Propuesta | COTIZACION_REGISTRADA | No |
| Rechazo | COTIZACION_RECHAZADA | No |
| Creación + propuesta | COTIZACION_REGISTRADA | Sí |
| Creación + rechazo | COTIZACION_RECHAZADA | Sí |

Una propuesta parcial ya contiene categoría y red; un rechazo parcial no las conoce. Referencia y fecha de creación son null hasta recibir creación. Los demás datos de creación, incluida política, se consultan en el fragmento opcional. Ausencia de ambos fragmentos significa ausencia de vista; no se permite un objeto vacío.

Las cuatro identidades deben coincidir. Creación y propuesta también deben coincidir en categoría/red. Dos resultados opuestos o el mismo hecho con contenido cambiado generan `ConflictoFragmentos`. Datos que no cumplen el contrato generan `DatosInvalidos`. Ningún fallo modifica la vista anterior.

Cada fragmento conserva procedencia. Mismo ID con contenido distinto es conflicto; nuevo ID con hecho equivalente conserva el fragmento original. Los productores deben mantener el ID original al reenviar: la segunda regla es defensiva. El modelo solo compara los fragmentos disponibles; los casos de uso añaden la comparación histórica del inbox, comprobada con dobles y con un inbox SQL durable. Dos fragmentos cargados tampoco pueden reutilizar un mismo event_id para hechos diferentes.

La revisión compatible de una propuesta no es una nueva versión de cotización ni un criterio para sobrescribir. El modelo acepta datos conocidos traducidos de una revisión posterior y conserva su procedencia; el alcance de transporte verificado es V1 y no usa duración. La combinación no compara relojes entre servicios y no calcula fechas locales de proyección. Las fechas de origen se normalizan a UTC.

Estos estados indican hechos recibidos. `COTIZACION_REGISTRADA` no confirma que Orquestación haya aplicado el resultado. Seguimiento no reevalúa catálogo/homologación ni puede verificar toda la cadena causal con los datos disponibles. La POC admite una sola petición por trabajo y no permite recotización.

## Casos de uso y transacción local

`componer_seguimiento(crear_unidad, reloj)` devuelve `proyectar_creacion` y `proyectar_resultado`. Reciben directamente `DatosCreacion` y `DatosResultadoCotizacion`, respectivamente, según sus firmas tipadas. Las validaciones de datos permanecen en los constructores del dominio; el adaptador de 05 traduce los mensajes externos a esos tipos. No se necesitan envoltorios de comandos. Cada invocación crea una UoW; los dos handlers usan la misma secuencia de `aplicacion/handlers/proyectar_fragmento.py` y la función de dominio `combinar`.

El consumidor lógico `seguimiento.proyeccion` es común a ambos handlers y las futuras réplicas. Inbox conserva el contenido normalizado de cada ID aceptado: un mensaje idéntico no escribe; otro ID equivalente confirma su entrada sin modificar la vista; un ID que reaparece alterado genera `ConflictoMensaje`. `ConflictoFragmentos` identifica conflictos empresariales, incluida una petición asociada a otro trabajo.

`dominio/repositorios.py` declara el puerto de persistencia. `aplicacion/unidad_trabajo.py` extiende el contrato transaccional de `seedwork/aplicacion/unidad_trabajo.py` con inbox y acceso a metadatos; no depende de SQL ni requiere salidas. `seedwork/aplicacion/reloj.py` es el puerto de reloj utilizado por ambos handlers. `MetadatosProyeccion`, en aplicación, conserva `primera_recepcion_en` y `proyectada_en` en UTC: la primera fecha es estable; la segunda cambia al incorporar un fragmento nuevo. Los duplicados no cambian ninguna.

Los dobles en `tests/unitarias/aplicacion/dobles/` mantienen un estado provisional y otro confirmado. Un fallo antes del commit descarta vista, fragmentos, inbox y fechas; se puede reintentar en una nueva UoW. Es rollback local, sin Saga ni compensaciones entre servicios. Estas pruebas con dobles no acreditan durabilidad tras reiniciar el proceso ni concurrencia SQL. El plan 04 añade los adaptadores SQL y acredita esas garantías mediante pruebas reales independientes de los dobles.

## PostgreSQL local

```bash
uv sync --locked
docker compose -f docker-compose.yaml up -d --wait postgres
export SEGUIMIENTO_DATABASE_URL='postgresql+psycopg://seguimiento:seguimiento_local@127.0.0.1:55435/seguimiento'
export SEGUIMIENTO_TEST_DATABASE_URL="$SEGUIMIENTO_DATABASE_URL"
uv run --locked alembic upgrade head
```

Compose crea PostgreSQL 17.6 en `127.0.0.1:55435` y un volumen propio. Las credenciales del ejemplo son del laboratorio local. La aplicación no carga `.env` automáticamente. Las migraciones se ejecutan explícitamente; el arranque no aplica migraciones automáticamente. El procesamiento depende de `SEGUIMIENTO_PROCESSING_ENABLED`.

`VistaSeguimientoSQL`, en `infraestructura/vistas.py`, conserva fragmentos JSONB, columnas derivadas y ambas fechas locales. `config/persistencia.py` registra metadata y crea la factoría de UoW; `componer_seguimiento_sql(base, reloj)` conecta esa factoría con los mismos handlers de 03. El reloj sigue siendo inyectable.

La gestión común está en el seedwork: contrato `UnidadTrabajo`, base `UnidadTrabajoSQL`, errores `ColisionPersistencia`/`ConflictoMensaje`, decorador `reintentar_colision` y utilidades de serialización. El módulo conserva `UnidadTrabajoSeguimientoSQL`, repositorio, metadatos, restricciones concretas y formato de fragmentos. El seedwork no importa módulos de negocio.

Cada UoW usa Session propia, aislamiento `READ COMMITTED` y flush explícito al confirmar, cuando vista y metadatos ya están completos. El repositorio bloquea la fila existente antes de combinar. Si dos operaciones insertan por primera vez, las restricciones identificadas permiten hasta tres intentos completos con UoW nueva, incluido inbox. Petición asociada a otro trabajo o contenido contradictorio termina en error.

El inbox usa `seguimiento.proyeccion` y conserva todos los mensajes aceptados, incluidos IDs equivalentes que no modifican la vista. Nada publica mensajes ni consulta a productores. Los consumidores del plan 05 invocan estos handlers desde lifespan.

## Consumo Pulsar V1

Preparar PostgreSQL como arriba y disponer del broker Pulsar. En el laboratorio actual se reutiliza el standalone de Entrada (`127.0.0.1:6650`); el script de preparación no arranca un broker. Para levantarlo desde el repositorio de referencia:

```bash
docker compose -f ../entrada-solicitudes-partner/docker-compose.yaml up -d --wait pulsar
export SEGUIMIENTO_PULSAR_URL='pulsar://127.0.0.1:6650'
export SEGUIMIENTO_PROCESSING_ENABLED=true
uv run --locked python scripts/preparar_pulsar.py
uv run --locked uvicorn seguimiento_trabajos.api.app:create_app --factory --host 127.0.0.1 --port 8003
```

El script registra los schemas provisionales documentados y prepara las suscripciones antes del tráfico. Con contratos de propietarios disponibles, cotejarlos antes de usar sus tópicos compartidos. Repetir preparación no mueve cursores. Los nombres de suscripción están centralizados en `config/rutas.py`; las réplicas comparten los mismos nombres.

Consultar `curl --fail http://127.0.0.1:8003/health/ready` desde otra terminal. Readiness es 200 cuando DB y las tres fuentes están operativas; 503 en modo técnico, recuperación, pausa o cierre. El timeout sin mensajes es normal. Un conflicto/Avro inválido conserva el mensaje sin ACK, pausa su fuente y muestra diagnóstico; liveness permanece disponible. Corregir la causa y reiniciar el servicio completo; con réplicas, detener la corrida inválida para evitar rotación del mensaje.

Detener con Ctrl+C o SIGTERM. El presupuesto compartido de cierre es 9 s; recepción predeterminada 500 ms, conexión/operaciones Pulsar 1 s. La factoría SQL utiliza pool timeout 1 s, conexión 2 s, `statement_timeout=1000`, `lock_timeout=500`, `transaction_timeout=2000` y `tcp_user_timeout=2000` ms. Son límites del laboratorio PostgreSQL 17; no configuran otros servidores. La parada espera a los hilos antes de liberar Engine. No se borra la DB ni se usa `unsubscribe` durante recuperación.

Para reproducir orden adverso, cortes de proceso, fan-out, concurrencia, corrupción y HTTP real:

```bash
uv run --locked pytest tests/integracion/test_pulsar.py -q --tb=short
```

El harness publica contratos V1, usa barreras para demorar creación y procesos que se terminan con SIGKILL antes/después del commit. No es un endpoint empresarial ni un worker desplegado por separado. La vista se consulta en SQL desde sesiones nuevas; los GET empresariales permanecen pendientes.

## Verificación local

```bash
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts migraciones
uv run --locked python scripts/verify_distribution.py
```

La suite conserva las 242 pruebas de 01–04, incluidas 51 PostgreSQL, y añade las pruebas de 05 documentadas en su evidencia. Verifican ambos órdenes, inbox, restricciones, bloqueos, colisiones concurrentes, rollback, metadatos y recuperación mediante procesos separados. La comprobación de distribución construye sdist y wheel, instala este último sin modo editable e importa desde fuera del árbol fuente. No hay workflow CI.

Para ejecutar solo pruebas sin infraestructura:

```bash
uv run --locked pytest tests/unitarias tests/api tests/contratos -q
```

La suite completa crea bases `seguimiento_test_<uuid>`, migra desde vacío y las elimina al terminar. Si falta PostgreSQL o Pulsar, falla; no omite integración. Los tests de Pulsar crean tópicos exclusivos `seguimiento-test-<uuid>-*`, conservan cursores entre reinicios y no tocan tópicos empresariales de Entrada. Esos tópicos de laboratorio quedan retenidos para inspección; no son los nombres del arranque operativo. Las pruebas de reinicio conservan una base de prueba entre procesos y luego el fixture la elimina. La base de desarrollo no se vacía. Detener la instancia local con `docker compose -f docker-compose.yaml stop postgres` conserva el volumen.

## Planes y evidencia

- [Planes 01–08 e índice](docs/plans/README.md).
- [Plan 01 implementado](docs/plans/01-base-tecnologica.md).
- [Evidencia de la base tecnológica](docs/evidencias/01-base-tecnologica.md).
- [Plan 02 implementado](docs/plans/02-modelo-vista-seedwork.md).
- [Evidencia del modelo](docs/evidencias/02-modelo-vista-seedwork.md).
- [Plan 03 implementado](docs/plans/03-casos-uso-idempotencia.md).
- [Evidencia de casos de uso e idempotencia](docs/evidencias/03-casos-uso-idempotencia.md).
- [Plan 05 implementado localmente](docs/plans/05-pulsar-lectores-v1.md).
- [Evidencia de consumo y recuperación](docs/evidencias/05-pulsar-lectores-v1.md).
- [Plan 04 implementado](docs/plans/04-postgresql-vista-inbox.md).
- [Evidencia de PostgreSQL y concurrencia](docs/evidencias/04-postgresql-vista-inbox.md).
- [Procedencia y copias de referencia](docs/referencias/README.md).

Los documentos comunes se incluyen en el repositorio para trabajar sin carpetas hermanas. Las referencias de Entrada son documentación y contratos del productor; no son una dependencia Python. Las fuentes originales del equipo se conservan en entrega4.
