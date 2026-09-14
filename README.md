# Seguimiento de Trabajos

Planes 01–03 implementados y verificados localmente: FastAPI con `/health/live`, configuración explícita, factoría SQLAlchemy/psycopg, estructura modular y seedwork local, pruebas aisladas y paquete instalable.

El modelo puro combina TrabajoCreado y los resultados de Cotizaciones en una vista inmutable. Los casos de uso coordinan proyección, inbox y metadatos mediante una UoW comprobada con dobles. Están pendientes persistencia durable en 04, consumidores en 05 y consultas en 06. La aplicación actual no inicia hilos ni se conecta a Pulsar; configurar una URL solo prepara la factoría SQL, sin ejecutar SQL.

## Instalación y ejecución

Requisitos: uv y Python 3.12. No se necesita Docker, PostgreSQL ni broker para este incremento.

```bash
uv sync --locked
uv run --locked uvicorn seguimiento_trabajos.api.app:create_app --factory --host 127.0.0.1 --port 8003
```

Desde otra terminal:

```bash
curl --fail --silent --show-error -i http://127.0.0.1:8003/health/live
```

Respuesta esperada: HTTP 200 y `{"status":"ok","service":"seguimiento-trabajos"}`. Detener con Ctrl+C. Liveness acredita que el proceso responde; todavía no hay readiness ni API de consultas de trabajos.

## Configuración

| Variable | Valor predeterminado | Uso |
|---|---|---|
| `SEGUIMIENTO_SERVICE_NAME` | `seguimiento-trabajos` | Identidad de liveness. |
| `SEGUIMIENTO_DATABASE_URL` | Vacía | Sin base configurada; para preparar Engine usar una URL `postgresql+psycopg://...`. |

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

El módulo separa datos y enumeraciones en `dominio/objetos_valor.py`, `VistaSeguimiento` en `dominio/vistas.py` y combinación pura en `dominio/servicios.py`. Seedwork contiene validaciones de UUID, enteros positivos, texto y fechas UTC, y la excepción común DatosInvalidos. Identidad, procedencia, creación y resultado utilizan esas validaciones; las reglas específicas permanecen en el módulo. La factoría recibe configuración, factoría de base y ciclo de procesamiento sustituibles. El ciclo predeterminado no hace operaciones. `config/bootstrap.py` compone los dos handlers con una factoría de UoW y reloj explícitos; no crea conexiones ni inicia procesamiento. No hay consumidores, bus ni outbox.

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

Cada fragmento conserva procedencia. Mismo ID con contenido distinto es conflicto; nuevo ID con hecho equivalente conserva el fragmento original. Los productores deben mantener el ID original al reenviar: la segunda regla es defensiva. El modelo solo compara los fragmentos disponibles; los casos de uso añaden la comparación histórica del inbox, actualmente probada con dobles. Dos fragmentos cargados tampoco pueden reutilizar un mismo event_id para hechos diferentes.

La revisión compatible de una propuesta no es una nueva versión de cotización ni un criterio para sobrescribir. El modelo acepta datos conocidos traducidos de una revisión posterior y conserva su procedencia; aún no consume Avro ni usa duración. La combinación no compara relojes entre servicios y no calcula fechas locales de proyección. Las fechas de origen se normalizan a UTC.

Estos estados indican hechos recibidos. `COTIZACION_REGISTRADA` no confirma que Orquestación haya aplicado el resultado. Seguimiento no reevalúa catálogo/homologación ni puede verificar toda la cadena causal con los datos disponibles. La POC admite una sola petición por trabajo y no permite recotización.

## Casos de uso y transacción local

`componer_seguimiento(crear_unidad, reloj)` devuelve `proyectar_creacion` y `proyectar_resultado`. Reciben directamente `DatosCreacion` y `DatosResultadoCotizacion`, respectivamente, según sus firmas tipadas. Las validaciones de datos permanecen en los constructores del dominio; el adaptador de 05 traducirá los mensajes externos a esos tipos. No se necesitan envoltorios de comandos. Cada invocación crea una UoW; los dos handlers usan la misma secuencia de `aplicacion/handlers/proyectar_fragmento.py` y la función de dominio `combinar`.

El consumidor lógico `seguimiento.proyeccion` es común a ambos handlers y las futuras réplicas. Inbox conserva el contenido normalizado de cada ID aceptado: un mensaje idéntico no escribe; otro ID equivalente confirma su entrada sin modificar la vista; un ID que reaparece alterado genera `ConflictoMensaje`. `ConflictoFragmentos` identifica conflictos empresariales, incluida una petición asociada a otro trabajo.

`dominio/repositorios.py` declara el puerto de persistencia. `aplicacion/unidad_trabajo.py` declara la transacción, inbox y acceso a metadatos; no depende de SQL ni requiere salidas. `seedwork/aplicacion/reloj.py` es el puerto de reloj utilizado por ambos handlers. `MetadatosProyeccion`, en aplicación, conserva `primera_recepcion_en` y `proyectada_en` en UTC: la primera fecha es estable; la segunda cambia al incorporar un fragmento nuevo. Los duplicados no cambian ninguna.

Los dobles en `tests/unitarias/aplicacion/dobles/` mantienen un estado provisional y otro confirmado. Un fallo antes del commit descarta vista, fragmentos, inbox y fechas; se puede reintentar en una nueva UoW. Es rollback local, sin Saga ni compensaciones entre servicios. Las pruebas no acreditan durabilidad tras reiniciar el proceso ni concurrencia SQL. Los adaptadores de persistencia reales siguen pendientes del plan 04.

## Verificación local

```bash
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
```

175 pruebas cubren la base tecnológica, el modelo y los casos de uso: 114 pruebas previas y 61 nuevas de aplicación, UoW e importación aislada. Incluyen los dos órdenes de llegada, duplicados, conflictos de mensaje/petición, fechas locales, rollback y reintento. La comprobación de distribución construye sdist y wheel, instala este último sin modo editable e importa desde fuera del árbol fuente. No hay workflow CI.

Comprobación del cliente candidato sin broker, separada de las dependencias del servicio:

```bash
uv run --isolated --no-project --python 3.12 --with pulsar-client==3.13.0 python -c 'import platform, importlib.metadata, pulsar; print(platform.platform()); print(importlib.metadata.version("pulsar-client")); print(pulsar.Client is not None)'
```

## Planes y evidencia

- [Planes 01–08 e índice](docs/plans/README.md).
- [Plan 01 implementado](docs/plans/01-base-tecnologica.md).
- [Evidencia de la base tecnológica](docs/evidencias/01-base-tecnologica.md).
- [Plan 02 implementado](docs/plans/02-modelo-vista-seedwork.md).
- [Evidencia del modelo](docs/evidencias/02-modelo-vista-seedwork.md).
- [Plan 03 implementado](docs/plans/03-casos-uso-idempotencia.md).
- [Evidencia de casos de uso e idempotencia](docs/evidencias/03-casos-uso-idempotencia.md).
- [Procedencia y copias de referencia](docs/referencias/README.md).

Los documentos comunes se incluyen en el repositorio para trabajar sin carpetas hermanas. Las referencias de Entrada son documentación y contratos del productor; no son una dependencia Python. Las fuentes originales del equipo se conservan en entrega4.
