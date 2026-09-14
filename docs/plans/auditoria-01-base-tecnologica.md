# Auditoría del plan 01 — Seguimiento de Trabajos

Fecha de referencia: 2026-09-13. Objeto: [plan 01](01-base-tecnologica.md), versión de 17 líneas. Auditoría documental contrastada con código y pruebas de Entrada. No modifica el plan ni implementa Seguimiento.

## Actualización posterior

Por solicitud de Nicolás se incorporaron H1–H6 al plan 01 y se sincronizaron la base común, el plan 05 y el estado de lifespan de Entrada en las decisiones comunes. La variante elegida para Seguimiento sigue `config/procesamiento.py` y `seedwork/infraestructura/ciclos.py`. Las líneas, hallazgos y verificaciones del informe siguiente describen la versión original auditada. Los ajustes son documentales: Seguimiento continúa pendiente de implementación.

## Ejecución posterior en este repositorio

El plan 01 ya fue implementado; ver la [evidencia local](../evidencias/01-base-tecnologica.md). El dictamen y los resultados de Entrada que siguen son el registro histórico de la auditoría previa.

## Dictamen

La dirección es correcta y debe conservarse. El plan aún necesita concretar alcance, estructura y cierre para tener el mismo nivel de preparación que el primer incremento de Entrada. No hace falta cambiar la arquitectura acordada ni agregar servicios.

Seguimiento debe comenzar con una base muy similar: paquete instalable con uv, FastAPI con factoría y lifespan sustituible, configuración aislada, Engine/sessionmaker síncronos con psycopg, pruebas sin infraestructura y comprobación del wheel. La diferencia funcional es deliberada: un módulo de proyección, sin los dos módulos empresariales, bus interno, outbox o publicadores de Entrada.

No existe todavía `entrega4/seguimiento-trabajos`. Los hallazgos son vacíos o ambigüedades de la documentación; no son errores reproducidos de ese servicio.

## Fuentes y precedencia

- Las nueve conversaciones revisadas en esta tarea: **Iniciar microservicio de partners**, **Revisa tutoriales de solución**, **Analiza POC de entrega 4**, **Audita el primer plan (2)**, **Audita el segundo plan**, **Audita el tercer plan**, **Auditar cuarto plan**, **Auditar quinto plan** y **Audita sexto plan**. Los identificadores originales están en la solicitud de auditoría. Se consideran las correcciones posteriores, no solamente las primeras propuestas.
- La confirmación en esta conversación del recorrido Entrada → Orquestación → Cotizaciones, con Seguimiento consumiendo TrabajoCreado y uno de los dos resultados posibles por petición.
- [Decisiones comunes](comun/00-decisiones-y-alcance.md), [base común](comun/02-base-de-implementacion.md), [contratos](comun/01-contratos-y-datos.md) y [secuencia de Seguimiento](README.md).
- [Plan 01 de Entrada](../referencias/entrada/01-base-tecnologica.md), [evidencia original](../referencias/entrada/evidencia-01-base-tecnologica.md), pyproject, factorías, configuración, pruebas y script de distribución actuales.

La base común ya resuelve varias decisiones; no se consideran ausentes de todo el diseño. Los hallazgos señalan dónde el incremento 01 debe concretarlas o evitar instrucciones contradictorias. No se reauditaron Coursera, NotebookLM ni la rúbrica en esta fase.

## Hallazgos

### H1 — P2: el objetivo y el trabajo mezclan el producto final con el incremento 01

**Evidencia:** líneas 7 y 11: servicio que mantiene su base desde Pulsar y administración de tres consumidores. Las líneas 15 y 17 aclaran después que todavía no hay proyección durable y que el consumo real llega en 05.

**Riesgo:** implementar conexiones, hilos consumidores y persistencia antes de sus modelos y adaptadores, o cerrar 01 sin saber qué parte debía funcionar. El cierre posterior limita el alcance, pero la redacción inicial apunta a otro resultado.

**Ajuste:** formular el objetivo como «entregar un paquete instalable, una API comprobable sin infraestructura y la base de configuración/persistencia para Seguimiento». En 01 preparar la composición con un ciclo de procesamiento falso o sin operaciones; en 05 conectar los tres consumidores reales. Sustituir «si aplica, despacho» por una referencia exclusiva al consumo: este servicio no despacha mensajes.

**Cierre:** un arranque local responde `/health/live` sin PostgreSQL ni Pulsar. No existen aún consultas de trabajos ni actualización de vistas. El procesamiento real sigue pendiente de 05.

### H2 — P2: falta traducir la estructura común a un árbol concreto de Seguimiento

**Evidencia:** línea 9 enumera algunos archivos sin `src/seguimiento_trabajos`, módulos, seedwork, suites, README o la ubicación de los planes dentro del futuro repositorio. La base común aporta un árbol genérico con piezas que Seguimiento no necesita. Además propone `infraestructura/ciclo_vida.py`, mientras Entrada usa `config/procesamiento.py` y `seedwork/infraestructura/ciclos.py`.

**Riesgo:** repetir los cambios de organización de Entrada o copiar clases, módulos y scripts que dependen de funcionalidades posteriores. Las dos ubicaciones de ciclo de vida son válidas, pero no deben implementarse simultáneamente por seguir documentos distintos.

**Ajuste:** fijar el árbol específico y las responsabilidades antes de ejecutar. Recomiendo conservar `config/bootstrap.py` para ensamblaje y adoptar, cuando llegue 05, la organización de procesamiento de Entrada. Si se adopta esta recomendación, actualizar explícitamente la excepción en la base común; no agregar una capa paralela. En 01 no se necesitan los bucles reales.

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
    config/bootstrap.py                 # cuando tenga ensamblaje real
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

Las llaves son abreviación documental. Crear paquetes mínimos importables; no clases vacías para llenar el árbol. Seedwork adquiere abstracciones utilizadas en los siguientes incrementos. Llevar copias de los planes al repositorio autónomo con enlaces adaptados; no dejar referencias rotas a hermanos ni cambiar contratos públicos al renombrar el paquete.

**Cierre:** el README explica cada ubicación. El wheel importa únicamente paquetes existentes en 01. No se importa `solicitudes_partner` ni se introduce una biblioteca compartida.

### H3 — P2: «health con falsos» no concreta todas las pruebas del ciclo de vida

**Evidencia:** línea 13 menciona importación, creación, falsos y Engine. La base común pide inicio/cierre con falsos, pero el incremento no fija casos para excepciones, configuración o aislamiento entre aplicaciones. Entrada los verifica en test_app.py (referencia histórica externa: `entrada-solicitudes-partner/tests/api/test_app.py`), test_isolation.py (referencia histórica externa: `entrada-solicitudes-partner/tests/unitarias/test_isolation.py`) y test_database.py (referencia histórica externa: `entrada-solicitudes-partner/tests/unitarias/test_database.py`).

**Riesgo:** pasar las pruebas gracias a servicios locales o a un falso que evita ejecutar lifespan; filtrar recursos o compartir overrides entre aplicaciones.

**Ajuste y cierre:** exigir pruebas que demuestren:

1. Importación, creación, inicio y cierre en un intérprete limpio, sin configuración de infraestructura, con conexiones externas bloqueadas.
2. `GET /health/live` devuelve 200 y cuerpo estable con identidad de Seguimiento; no consulta infraestructura.
3. Dos aplicaciones no comparten recursos ni overrides; limpiar los overrides usados en pruebas.
4. Con URL configurada y factorías falsas, entrar/salir del procesamiento y cerrar la base incluso ante excepción. Probar también fallo al iniciar el procesamiento después de crear la base.
5. La factoría SQL real exige `postgresql+psycopg`, crea sesiones distintas sin conectar y dispone del Engine al cerrar. No compartir Session entre operaciones.
6. Importar la base técnica de persistencia no carga Pulsar. Ampliar esta comprobación a repositorios/proyección cuando existan en 04.

Usar `with TestClient(app)` para ejecutar de verdad el lifespan, según la [documentación oficial de FastAPI](https://fastapi.tiangolo.com/advanced/testing-events/), consultada mediante find-docs. Los falsos prueban composición; no acreditan commit, rollback, ACK ni recuperación del broker.

### H4 — P2: compatibilidad y empaquetado necesitan una evidencia definida

**Evidencia:** línea 9 exige Python/cliente compatibles y la línea 15 pide documentar versiones, pero no precisa el manifiesto de comprobación. La base común ofrece referencias de versiones. El pyproject actual de Entrada (referencia histórica externa: `entrada-solicitudes-partner/pyproject.toml`) incluye además dependencias y excepciones de tipado incorporadas en incrementos posteriores.

**Riesgo:** copiar el manifiesto completo o un lockfile con identidad de Entrada, asumir que el cliente nativo instala en otra plataforma, o reutilizar el script actual de distribución que importa agregados, publicadores y proyecciones inexistentes en 01.

**Ajuste:** tomar Python 3.12 y la combinación probada de Entrada como referencia; resolver el lockfile propio con uv. Incorporar FastAPI, Uvicorn, SQLAlchemy, psycopg y herramientas de prueba/calidad. Alembic y los adaptadores Pulsar reales corresponden a 04/05. La instalación/importación del cliente candidato se verifica temprano en un entorno aislado, aunque todavía no se integre al servicio.

Entrada documenta `httpx2` como ajuste real de TestClient; no reemplazarlo por `httpx` por copiar una propuesta anterior. Confirmar con la resolución elegida y un test HTTP. Tampoco copiar las excepciones mypy de esquemas Pulsar antes de que existan esos esquemas.

**Cierre:** registrar Python, SO, arquitectura, uv, versión candidata de Pulsar, comandos y resultados de instalación/importación. Adaptar el script de distribución para construir/instalar el wheel no editable e importarlo fuera del árbol fuente, verificando la ruta instalada. Esto no certifica Avro, broker ni compatibilidad v1/v2.

### H5 — P2: CI reaparece sin distinguir la decisión anterior de verificaciones locales

**Evidencia:** línea 9 incluye CI; la base común también lo menciona. En **Audita el primer plan (2)** Nicolás pidió quitar GitHub del incremento de Entrada y la implementación retiró el workflow.

**Riesgo:** añadir configuración remota que no forma parte del primer incremento de referencia y volver a declarar un cierre pendiente de ejecución externa.

**Ajuste recomendado:** mantener pruebas, lint, formato, tipos y distribución locales en 01. Retirar CI de su lista de entregables y armonizar la base común para este incremento. El antecedente es una decisión sobre Entrada; la recomendación de extenderla aquí responde a la similitud solicitada, no a una prohibición global de CI.

**Cierre:** README y evidencia permiten reproducir todos los checks localmente. No crear workflow, repositorio remoto ni hacer commit/push por ejecutar este plan.

### H6 — P2: «checks iniciales verdes» no define el cierre reproducible

**Evidencia:** línea 15. La base común enumera comandos de Entrada y advierte que no se asuman válidos para los repositorios nuevos. El incremento no concreta cuáles debe configurar ni cómo probar el arranque manual.

**Ajuste:** registrar comandos propios para sincronización bloqueada, suites de unidad/API, Ruff, mypy y distribución. Incluir `scripts` en el tipado como ya hace Entrada; no incluir `migraciones` mientras no exista. Documentar también la prueba HTTP real y parada.

**Comandos previstos, pendientes de implementar en Seguimiento:**

```bash
uv sync --locked
uv run --locked pytest tests/unitarias tests/api -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
```

**Arranque manual previsto, no check de terminación automática:**

```bash
uv run --locked uvicorn seguimiento_trabajos.api.app:create_app --factory --host 127.0.0.1 --port 8003
```

Desde otra terminal comprobar `/health/live`, registrar código/cuerpo y detener el proceso. El puerto 8003 es local; despliegue queda para 08. La evidencia debe diferenciar configuración, ejecución y resultado observado; no heredar el conteo de tests de Entrada.

## Qué conservar y qué no copiar de Entrada

| Pieza | Decisión para Seguimiento |
|---|---|
| Factoría FastAPI y dependencias explícitas | Conservar el patrón; adaptar identidad y evitar endpoints de solicitudes. |
| Settings | Leer entorno al construir configuración; usar `SEGUIMIENTO_*`, sin heredar `PARTNER_*` ni sus tópicos. |
| Engine y sessionmaker | Misma organización y driver, con recursos locales al servicio. |
| Módulos/capas y seedwork | Conservar estructura; un módulo `seguimiento`, abstracciones mínimas. |
| Lifespan | Preparar sustitución por falsos en 01; tres consumidores reales en 05. |
| Solicitudes y Reglas | No copiar: sus agregados y comunicación interna pertenecen a Entrada. |
| Outbox, bus local y publicación CQRS | No copiar: Seguimiento consume hechos y actualiza su vista privada. |
| Inbox y vista | Implementar en 03/04, no adelantar para cerrar la base tecnológica. |
| Script de distribución | Adaptar mecanismo; retirar imports que presuponen planes 02–06 terminados. |
| Tests y comandos | Reutilizar comportamientos verificables; fijar nombres y rutas propios. |

## Observaciones en documentos relacionados

- D08 y el cierre de [decisiones comunes](comun/00-decisiones-y-alcance.md) aún describen como pendiente la adaptación operativa de Entrada. El código actual de `api/app.py` y `config/procesamiento.py` ya ejecuta sus cuatro actividades desde lifespan. Corregir ese estado documental cuando se actualicen los planes; la integración grupal sigue pendiente.
- La estructura de procesamiento propuesta por la base común difiere de la construida en Entrada. Resolver H2 una vez y sincronizar 01, 05 y la base común, sin duplicar organizadores de ciclo de vida.
- E3, los contratos de Cotizaciones y la combinación de resultados permanecen fuera del primer incremento. Esta auditoría no modifica el diagrama confirmado ni reabre esos acuerdos.

## Verificación realizada

Ejecutado en el repositorio existente de Entrada:

```bash
uv run --locked pytest tests/api/test_app.py tests/unitarias/test_database.py tests/unitarias/test_settings.py tests/unitarias/test_isolation.py -q --tb=short
```

Resultado: **15 pruebas aprobadas**, una advertencia de deprecación de Starlette/AnyIO. Es una comprobación focalizada de la base de referencia, no la suite completa ni una validación de Seguimiento. La evidencia histórica de 14 pruebas corresponde a otra etapa y no se sustituyó.

Se leyeron el código vigente, documentación y conversaciones disponibles, y se comprobaron los enlaces relativos del informe. No se ejecutaron PostgreSQL/Pulsar, distribución ni despliegue. No se tocaron los cambios preexistentes de Entrada. El único archivo creado por esta auditoría es este informe.

## Recomendación

Incorporar H1–H6 al plan antes de implementarlo, conservando la secuencia 01–08. El resultado de 01 debe parecerse al primer incremento de Entrada en estructura, configuración y verificaciones, con la composición preparada para un servicio consumidor de tres tipos de eventos. No copiar el estado funcional completo que Entrada alcanzó en sus seis primeros planes.
