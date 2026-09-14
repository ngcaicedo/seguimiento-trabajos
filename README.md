# Seguimiento de Trabajos

Plan 01 implementado y verificado localmente: FastAPI con `/health/live`, configuración explícita, factoría SQLAlchemy/psycopg, estructura modular y seedwork local, pruebas aisladas y paquete instalable.

El servicio proyectará TrabajoCreado y los resultados de Cotizaciones en una vista privada. Esa funcionalidad todavía no está implementada: modelos en 02, casos de uso en 03, persistencia/inbox en 04, consumidores en 05 y consultas en 06. La aplicación actual no inicia hilos ni se conecta a Pulsar; configurar una URL solo prepara la factoría SQL, sin ejecutar SQL.

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
  modulos/seguimiento/{dominio,aplicacion,infraestructura}/
  seedwork/{dominio,aplicacion,infraestructura}/
tests/{unitarias,api,integracion,contratos}/
scripts/verify_distribution.py
docs/plans/
docs/plans/comun/
docs/evidencias/
docs/referencias/
```

Módulo y seedwork son paquetes mínimos; las abstracciones se añadirán con usos reales. La factoría recibe configuración, factoría de base y ciclo de procesamiento sustituibles. El ciclo predeterminado no hace operaciones. No se han creado `bootstrap.py`, consumidores, bus, outbox ni agregados ficticios para llenar carpetas.

## Verificación local

```bash
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
```

21 pruebas cubren configuración, sesiones independientes, importación sin red/Pulsar, health, overrides y liberación de recursos incluso ante fallos de inicio/cierre. La comprobación de distribución construye sdist y wheel, instala este último sin modo editable e importa desde fuera del árbol fuente. No hay workflow CI.

Comprobación del cliente candidato sin broker, separada de las dependencias del servicio:

```bash
uv run --isolated --no-project --python 3.12 --with pulsar-client==3.13.0 python -c 'import platform, importlib.metadata, pulsar; print(platform.platform()); print(importlib.metadata.version("pulsar-client")); print(pulsar.Client is not None)'
```

## Planes y evidencia

- [Planes 01–08 e índice](docs/plans/README.md).
- [Plan 01 implementado](docs/plans/01-base-tecnologica.md).
- [Evidencia de ejecución](docs/evidencias/01-base-tecnologica.md).
- [Procedencia y copias de referencia](docs/referencias/README.md).

Los documentos comunes se incluyen en el repositorio para trabajar sin carpetas hermanas. Las referencias de Entrada son documentación y contratos del productor; no son una dependencia Python. Las fuentes originales del equipo se conservan en entrega4.
