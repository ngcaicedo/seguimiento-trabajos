# 01 — Base tecnológica y pruebas aisladas

Estado: implementado y verificado localmente. [Evidencia de ejecución](../evidencias/01-base-tecnologica.md). Ajustes H1–H6 de la [auditoría](auditoria-01-base-tecnologica.md) incorporados. Dependencia local: ninguna.

## Objetivo y alcance

Entregar un paquete Python instalable y reproducible, una aplicación FastAPI comprobable sin infraestructura y la base de configuración y persistencia de Seguimiento. Usar como referencia la [base implementada de Entrada](../referencias/entrada/01-base-tecnologica.md), adaptando identidad, estructura y pruebas al servicio nuevo.

Repositorio previsto: `entrega4/seguimiento-trabajos`; paquete `seguimiento_trabajos`; módulo `seguimiento`; variables `SEGUIMIENTO_*`; puerto local 8003.

Este incremento entrega `/health/live`, factorías, configuración, empaquetado y pruebas aisladas. Prepara lifespan con procesamiento sustituible y sin operaciones reales. Los modelos llegan en 02, los casos de uso en 03, PostgreSQL e inbox en 04, los tres consumidores reales en 05 y las consultas de trabajos en 06. Todavía no hay proyección durable ni integración grupal.

Seguimiento consume TrabajoCreado y los resultados de Cotizaciones según los [contratos](comun/01-contratos-y-datos.md). No produce mensajes en este alcance: no requiere outbox, publicador, bus interno ni un segundo módulo empresarial.

## Decisiones técnicas

| Pieza | Decisión |
|---|---|
| Python | 3.12 como referencia; confirmar instalación/importación del cliente Pulsar candidato en la plataforma elegida antes de fijarlo. |
| uv | Proyecto con layout `src`, backend de empaquetado y lockfile propio generado por uv. No copiar el lockfile de Entrada. |
| FastAPI | Factoría `create_app`, configuración y factorías de recursos explícitas, lifespan sustituible en tests. |
| SQLAlchemy | API 2.x, Engine/sessionmaker con driver psycopg desde 01, sin abrir conexiones al construirlos. |
| Sesiones | Session síncrona independiente por operación; Engine y pool pueden vivir durante el proceso. No Session global compartida. |
| Tests | pytest y TestClient compatible con la resolución elegida. Entrada usa `httpx2`; verificarlo mediante un test HTTP, no sustituirlo por una propuesta antigua de `httpx`. |
| Calidad | Ruff, formato, mypy estricto y verificación de distribución locales. CI no es entregable de este incremento. |
| Migraciones y mensajería | Alembic y persistencia real en 04; adaptadores Pulsar en 05. La comprobación temprana del cliente se hace en un entorno aislado sin broker. |

No conectar al importar módulos ni al crear la aplicación. Leer variables al solicitar la configuración; evitar valores capturados globalmente. `SEGUIMIENTO_SERVICE_NAME` identifica el servicio y `SEGUIMIENTO_DATABASE_URL` vacía permite el arranque básico sin infraestructura. La URL configurada usa `postgresql+psycopg`. Las futuras variables de mensajería pertenecen a Seguimiento; no heredar `PARTNER_*`, tópicos ni suscripciones de Entrada.

En 01, incluso con URL configurada, el procesamiento predeterminado no realiza operaciones; los tests usan factorías falsas para ejercitar su ciclo de vida. Al integrar 05 se conectará el procesamiento operativo al entrar en lifespan. El modo básico sin base acredita liveness, no disponibilidad funcional del servicio de consultas.

## Organización de archivos

```text
seguimiento-trabajos/
  pyproject.toml
  uv.lock
  .python-version
  .env.example
  .gitignore
  README.md
  src/seguimiento_trabajos/
    __init__.py
    py.typed
    api/app.py
    config/settings.py
    config/database.py
    modulos/seguimiento/{dominio,aplicacion,infraestructura}/
    seedwork/{dominio,aplicacion,infraestructura}/
  tests/unitarias/
  tests/api/
  tests/integracion/
  tests/contratos/
  scripts/verify_distribution.py
  docs/plans/
  docs/evidencias/
```

Las llaves son abreviación documental. Crear paquetes mínimos importables con los `__init__.py` necesarios, sin clases vacías. Seedwork se desarrolla con usos reales desde 02. Conservar el vocabulario español acordado y los nombres técnicos `src`, `api`, `config`, `seedwork` y `tests`.

| Archivo | Responsabilidad |
|---|---|
| `api/app.py` | Factoría, endpoint de liveness y ciclo de vida con colaboradores sustituibles. |
| `config/settings.py` | Configuración inmutable leída explícitamente del entorno. |
| `config/database.py` | Factoría de Engine/sessionmaker y liberación de recursos propios. |
| `scripts/verify_distribution.py` | Construir/instalar el wheel e importar sus paquetes fuera del árbol fuente. |
| `tests/unitarias/test_settings.py` | Defaults, lectura diferida, prefijo propio y URL vacía. |
| `tests/unitarias/test_database.py` | Driver explícito, sesiones independientes y cierre sin conexión. |
| `tests/unitarias/test_isolation.py` | Importación y lifespan sin red en intérprete limpio; aislamiento frente a Pulsar. |
| `tests/api/test_app.py` | Health, overrides independientes y recursos liberados incluso ante errores. |

Cuando haya ensamblaje real se añade `config/bootstrap.py`. En 05, seguir la organización de Entrada: `config/procesamiento.py` conecta el ciclo de vida y `seedwork/infraestructura/ciclos.py` administra los hilos reutilizables. No crear además `infraestructura/ciclo_vida.py`. Cada componente conserva las responsabilidades de la [base común](comun/02-base-de-implementacion.md).

Al crear el repositorio, incorporar sus planes en `docs/plans` y adaptar sus enlaces. Incluir allí las referencias comunes necesarias para que la documentación sea utilizable sin depender de carpetas hermanas; los contratos conservan procedencia y versión. No importar código de Entrada.

## Trabajo y pruebas

1. Inspeccionar la carpeta de destino y conservar cualquier contenido existente. Registrar Python, SO, arquitectura, uv y cliente Pulsar candidato; comprobar instalación/importación del cliente en un entorno aislado sin broker. La referencia probada en Entrada es Python 3.12 y cliente 3.13.0; no implica que sean las últimas versiones ni garantiza otra plataforma.
2. Crear el proyecto y configurar empaquetado, dependencia de psycopg y herramientas locales. Resolver versiones con uv y generar el lockfile propio. No copiar dependencias, excepciones mypy o imports de esquemas de incrementos posteriores de Entrada.
3. Red: escribir los casos de configuración, API, factoría SQL y aislamiento descritos abajo. Registrar un fallo significativo por comportamiento o componentes pendientes antes de implementar.
4. Green: implementar lo mínimo para que pasen, con configuración explícita, liveness y factorías sustituibles. Refactorizar con las pruebas en verde.
5. Configurar clasificación de suites, Ruff y mypy incluyendo `scripts`; las suites futuras de integración/contratos no necesitan tests ficticios. Crear `.env.example` sin secretos y `.gitignore`.
6. Adaptar el mecanismo de distribución de Entrada. Construir e instalar el wheel de forma no editable en un entorno temporal con dependencias bloqueadas; importar desde fuera del árbol fuente y verificar que la ruta pertenece al entorno instalado. Comprobar solo paquetes y funciones que existan en 01, sin copiar los imports de agregados, publicadores o proyecciones de su script actual.
7. Documentar instalación, checks, arranque/parada y límites en README. Registrar resultados y plataforma en `docs/evidencias/01-base-tecnologica.md`.

### Casos obligatorios de cierre

- Importar, crear, iniciar y cerrar la app en un intérprete limpio sin variables obligatorias de infraestructura, bloqueando conexiones externas para detectar cualquier intento accidental.
- Usar `with TestClient(app)` para ejecutar inicio/cierre, no solamente construir el cliente. `/health/live` devuelve 200 y `{"status":"ok","service":"seguimiento-trabajos"}` con configuración predeterminada, sin consultar dependencias externas.
- Dos aplicaciones mantienen recursos y overrides independientes. Limpiar los overrides utilizados y verificar que la configuración se lee al solicitarla.
- Sin URL no se invoca la factoría de base. Con URL y colaboradores falsos se entra y sale del procesamiento, se libera la base y se limpia el estado al terminar.
- Verificar cierre normal, excepción durante uso y fallo al iniciar el procesamiento después de crear la base. Los recursos ya adquiridos se liberan sin compartirlos con otra aplicación.
- Construir el Engine/sessionmaker real con psycopg y una URL de prueba sin servidor; obtener sesiones distintas, bloquear cualquier conexión y disponer del Engine al cerrar. Rechazar dialectos/driver diferentes. No ejecutar SQL.
- Importar la base técnica de persistencia con imports de Pulsar bloqueados. En 04 ampliar la prueba a repositorios y proyección, cuando existan.
- Instalar/importar el cliente nativo candidato y registrar la plataforma. Esto no acredita interoperabilidad con broker, Avro ni evolución v1/v2.
- Instalar/importar el wheel fuera del árbol fuente; ejecutar unitarias/API, lint, formato y tipos sin Docker.

Los dobles prueban composición y liberación de recursos; no prueban atomicidad, commit, rollback, ACK ni recuperación. El dominio y aplicación futuros se mantendrán aislados de FastAPI, SQLAlchemy y Pulsar.

## Verificación prevista

Configurar y ejecutar desde la raíz del nuevo repositorio:

```bash
uv sync --locked
uv run --locked pytest tests/unitarias tests/api -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
```

No incluir `migraciones` en mypy antes de crear esa ruta en 04. No crear workflows ni exigir ejecución remota para cerrar 01. Antes de cualquier commit/push solicitado ejecutar la suite completa vigente; este plan no autoriza publicar cambios.

Para verificar HTTP real, iniciar en una terminal:

```bash
uv run --locked uvicorn seguimiento_trabajos.api.app:create_app --factory --host 127.0.0.1 --port 8003
```

En otra terminal:

```bash
curl --fail --silent --show-error -i http://127.0.0.1:8003/health/live
```

Registrar código y cuerpo, y detener Uvicorn con Ctrl+C. El servidor es un comando de larga duración, no un check que termina solo. En el despliegue de 08 se escuchará en `0.0.0.0` y el puerto suministrado por `PORT`.

## Criterio de cierre

Todos los casos obligatorios pasan; el paquete se instala fuera del árbol fuente; README y evidencia registran versiones, plataforma, comandos y resultados realmente observados. El arranque HTTP local responde y se detiene correctamente. No heredar conteos de pruebas de Entrada ni presentar verificaciones futuras como ejecutadas.

Se conserva un proceso FastAPI por instancia. Este incremento prepara la composición; 05 inicia y cierra tres hilos consumidores del mismo proceso, con sesiones por operación y sin bloquear HTTP. Seguimiento no tiene despacho ni outbox. La proyección durable, consultas e integración siguen pendientes de los incrementos correspondientes.

Referencia de pruebas de ciclo de vida verificada durante la auditoría: [FastAPI — Testing Events](https://fastapi.tiangolo.com/advanced/testing-events/). Al ejecutar, consultar documentación actualizada con find-docs para concretar configuración y versiones de herramientas.
