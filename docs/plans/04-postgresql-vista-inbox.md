# 04 — PostgreSQL, fragmentos e inbox

Estado: implementado y verificado localmente. [Evidencia y límites](../evidencias/04-postgresql-vista-inbox.md). Ajustes H1–H6 de la [auditoría](auditoria-04-postgresql-vista-inbox.md) incorporados. Servicio: seguimiento. Ver [modelo y secuencia](README.md), [base común](comun/02-base-de-implementacion.md) y [contratos](comun/01-contratos-y-datos.md).

Dependencia local: [03](03-casos-uso-idempotencia.md).

## Objetivo y alcance

Persistir vista, fragmentos, metadatos locales e inbox en PostgreSQL, usando los casos de uso y puertos implementados en 03. Demostrar atomicidad, concurrencia y recuperación tras reiniciar el proceso.

`VistaSeguimiento` permanece en `dominio/vistas.py` y `combinar` en `dominio/servicios.py`. Infraestructura almacena y reconstruye ese modelo; no decide nuevamente sus reglas. Seguimiento describe hechos recibidos y no confirma que Orquestación haya aplicado el resultado.

Una BD privada contiene la proyección y el inbox. Este incremento no añade Saga, outbox, bus interno, publicador, consultas a productores, otra BD de lectura ni roles SQL por capa. Consumidores/Avro/ACK corresponden a 05; consultas HTTP y duración v2 a 06. No conectar procesamiento operativo al lifespan antes de 05.

## Organización y contratos

Rutas relativas a `src/seguimiento_trabajos/`, salvo archivos de raíz y pruebas:

| Archivo | Responsabilidad |
|---|---|
| `modulos/seguimiento/infraestructura/vistas.py` | `VistaSeguimientoSQL`: representación ORM, columnas, restricciones e índices. No duplicar la clase en otro `orm.py` del módulo. |
| `modulos/seguimiento/infraestructura/repositorios.py` | Implementar `RepositorioSeguimiento`; consultar con bloqueo, guardar vista y gestionar metadatos SQL. |
| `modulos/seguimiento/infraestructura/mapeadores.py` | Convertir fila y fragmentos a tipos propios; derivar columnas desde la vista validada. |
| `modulos/seguimiento/infraestructura/serializacion.py` | Formato durable de los fragmentos, independiente del transporte Avro. |
| `modulos/seguimiento/infraestructura/unidad_trabajo.py` | Extender la base SQL del seedwork con repositorio, fragmentos, metadatos y nombres de restricciones de Seguimiento. |
| `seedwork/infraestructura/orm.py` | Base ORM local compartida por vista e inbox. |
| `seedwork/infraestructura/inbox.py` | Tabla y operación transaccional de inserción/comparación del documento por mensaje. |
| `seedwork/aplicacion/unidad_trabajo.py` | Contrato básico de contexto, confirmación y reversión; el puerto específico de Seguimiento lo extiende. |
| `seedwork/aplicacion/excepciones.py` | `ColisionPersistencia` y `ConflictoMensaje`, independientes del módulo. |
| `seedwork/aplicacion/reintentos.py` | Repetir una operación completa ante colisiones, con máximo de tres intentos. |
| `seedwork/infraestructura/unidad_trabajo_sqlalchemy.py` | Base SQL: sesión, transacción, flush, commit, rollback, cierre y traducción de restricciones declaradas por la especialización. |
| `seedwork/infraestructura/serializacion.py` | `Documento`, normalización JSON de UUID/fechas y lectura tipada de valores básicos. |
| `modulos/seguimiento/aplicacion/handlers/proyectar_fragmento.py` | Coordinar la proyección usando el decorador de reintentos del seedwork; mantener `combinar` como única regla de combinación. |
| `config/bootstrap.py` | Ampliar la composición existente con una factoría de UoW SQL y reloj; sin SQL ni reglas empresariales. |
| `config/persistencia.py` | Registrar metadata y construir la factoría SQL usada por bootstrap, migraciones y pruebas. |
| `alembic.ini`, `migraciones/env.py`, `migraciones/versions/0001_seguimiento.py` | Configuración y primera migración del esquema privado. |
| `docker-compose.yaml`, `.env.example`, `pyproject.toml`, `uv.lock` | PostgreSQL local, variables documentadas y dependencia de Alembic. |
| `tests/integracion/` | Fixture de BD, migraciones, serialización SQL, UoW, proyección, concurrencia y reinicio. |

Implementar todas las operaciones de `UnidadTrabajoSeguimiento`: contexto, repositorio, `preparar_entrada`, `obtener_metadatos`, `guardar_metadatos`, `confirmar` y `revertir`. Los handlers siguen recibiendo directamente `DatosCreacion` o `DatosResultadoCotizacion`; no recrear envoltorios de comandos.

La base `UnidadTrabajoSQL` del seedwork crea y cierra una Session por invocación y por reintento. Repositorios e inbox reciben esa misma Session y nunca hacen commit ni rollback global por su cuenta. La base coordina la transacción y la UoW concreta delega la E/S del módulo; no requiere `EventoDominio`, destinos ni salidas de Entrada. No compartir Session entre hilos ni crear un proyector SQL paralelo a los handlers.

## Modelo SQL y reconstrucción

La tabla `seguimiento_trabajos` contiene:

| Campos | Persistencia y semántica |
|---|---|
| `id_trabajo` | UUID, PK con nombre `pk_seguimiento_trabajos`. |
| `id_peticion` | UUID obligatorio, UNIQUE `uq_seguimiento_peticion`. Una petición no pertenece a dos trabajos. |
| `id_solicitud`, `id_partner` | UUID obligatorios; conservar los IDs recibidos, sin nuevas restricciones de unicidad inferidas. |
| `fragmento_creacion`, `fragmento_resultado` | JSONB opcionales; ausencia representada como NULL SQL. CHECK `ck_seguimiento_fragmento_presente` exige al menos uno. |
| `estado`, `creacion_recibida` | Obligatorios y derivados de las propiedades del modelo validado. |
| `categoria`, `tipo_red`, `referencia_externa`, `creado_en` | Columnas derivadas nullable; `creado_en` conserva zona horaria. No inventar datos cuando falta creación. |
| `primera_recepcion_en`, `proyectada_en` | Fechas locales obligatorias con zona horaria, normalizadas a UTC y gestionadas por la aplicación. |

Oferta, importe entero en unidades menores, moneda, motivo, política y versiones permanecen completos en sus fragmentos. No necesitan columnas duplicadas antes de que una consulta las requiera. Un rechazo parcial no conoce categoría/red/referencia; una propuesta parcial sí conoce categoría/red. La duración y su futura columna nullable pertenecen a 06.

Definir índices para `(primera_recepcion_en, id_trabajo)`, `(id_partner, primera_recepcion_en, id_trabajo)` y `(estado, primera_recepcion_en, id_trabajo)`. Soportan orden y filtros previstos; no implementar todavía consultas HTTP ni optimizaciones sin una necesidad medida.

Los fragmentos son la base de reconstrucción. El mapeador genera las columnas derivadas desde `VistaSeguimiento`, preservando coherencia con el contenido guardado. Una creación tardía conserva el resultado y completa la vista; no copiar el reemplazo de snapshots por versión del CQRS de Entrada. Tampoco comparar versiones de propietarios diferentes ni elegir un ganador por fecha.

La serialización conserva todos los campos de `DatosCreacion` y `DatosResultadoCotizacion`, incluidos identidad y `Procedencia`: tipo, event_id, revisión de contrato, instante, correlación y causación. Representar UUID como texto canónico, enumeraciones por su valor, fechas ISO 8601 UTC, importes/versiones como enteros y ausencias como null. Reconstruir mediante tipos propios validados, sin IDs, eventos ni relojes nuevos. Si se incluye revisión del formato de almacenamiento, distinguirla de la revisión del contrato público.

No restringir a revisión 1 una propuesta compatible que el modelo actual admite. La normalización debe conservar igualdad tras ida y vuelta y distinguir cambios de procedencia. Persistencia no importa Pulsar ni serializa bytes Avro; conserva únicamente los datos conocidos por el lector. Los fragmentos no forman un event store ni una plataforma de replay.

## Secuencia transaccional y concurrencia

Usar y verificar aislamiento PostgreSQL `READ COMMITTED`. Mantener el orden común a todos los handlers:

1. Abrir una UoW nueva y preparar/comparar inbox.
2. Si el ID ya está confirmado e idéntico, terminar correctamente sin nuevas escrituras. Ante contenido distinto, propagar `ConflictoMensaje`.
3. Obtener la vista por trabajo con bloqueo de fila hasta terminar la transacción. Si no existe, devolver ausencia: no insertar una fila vacía para bloquearla.
4. Ejecutar `combinar` en aplicación usando el modelo de dominio.
5. Si cambia la vista, guardar fragmentos/columnas, comprobar la asociación de petición y preparar sus metadatos locales. Si el hecho es equivalente con otro ID, conservar vista y fechas y confirmar solo el inbox nuevo.
6. Hacer flush y commit de todo el estado provisional; cerrar la Session. Un fallo o salida sin confirmar revierte todo.

`guardar(vista)` prepara la fila ORM; las operaciones siguientes de metadatos deben trabajar sin disparar un autoflush de esa fila incompleta. Completar ambas fechas antes del flush final. No resolverlo permitiendo filas confirmadas sin metadatos ni añadiendo fechas ficticias. Probar el orden real del handler, que consulta metadatos después de guardar la vista.

### Primera inserción y colisiones

El bloqueo de filas existentes no protege una fila todavía ausente. Dos mensajes con IDs distintos pueden encontrar el mismo trabajo ausente; la PK/UNIQUE resuelve cuál inserción se confirma primero. [PostgreSQL 17: bloqueos](https://www.postgresql.org/docs/17/explicit-locking.html#LOCKING-ROWS).

La UoW traduce únicamente violaciones identificadas de `pk_seguimiento_trabajos` y `uq_seguimiento_peticion` a la colisión reintentable propia, después de revertir y cerrar. No capturar cualquier `IntegrityError` como duplicado. Otras restricciones o errores técnicos se propagan; no producen éxito.

La coordinación compartida admite **hasta tres intentos totales**, cada uno desde la preparación de inbox y con UoW nueva. Conservar el fragmento original, sus IDs y procedencia. Reintentar la operación completa, no solamente `guardar`: el rollback descartó también el inbox y las fechas provisionales. Al agotar intentos, propagar el error técnico. [SQLAlchemy 2.0: rollback tras fallo de flush](https://docs.sqlalchemy.org/en/20/faq/sessions.html).

El repositorio verifica la asociación de petición antes de insertar/guardar, sin provocar flush prematuro. Si una transacción concurrente gana esa asociación, el siguiente intento debe releerla: petición ligada a otro trabajo produce `ConflictoFragmentos`; mismo trabajo permite cargar con bloqueo y combinar/reconocer el hecho. PK y UNIQUE siguen protegiendo la carrera aunque una consulta previa no vea al competidor. No reintentar conflictos de mensaje ni empresariales.

El contador de reintentos no contiene SQL ni vuelve a implementar la combinación. Registrar y probar agotamiento, renovación de UoW y conservación de identidad. El futuro adaptador de 05 solo podrá hacer ACK cuando el caso de uso termine correctamente.

## Inbox durable

Tabla `inbox` con clave única `(consumidor_logico, event_id)` y documento JSONB obligatorio. Usar siempre `seguimiento.proyeccion`, compartido por ambos handlers y todas las réplicas. No incorporar tipo de evento, revisión de lector, réplica o nombre de suscripción a esa clave.

`preparar_entrada` recibe el fragmento normalizado y conserva el contrato de 03: verdadero para entrada nueva provisional, falso para entrada idéntica confirmada, `ConflictoMensaje` para contenido diferente. La inserción y comparación deben resolver también la recepción simultánea del mismo ID en PostgreSQL. No sobrescribir el documento anterior.

Guardar el contenido propio completo de cada mensaje aceptado, aunque no cambie la vista:

| Recepción | Resultado durable |
|---|---|
| A: propuesta válida | Vista/fragmento, metadatos e inbox A. |
| A idéntico | Mismo estado confirmado; sin segunda entrada ni cambio de fechas. |
| B: nuevo ID, mismo hecho | Inbox B adicional; vista, fragmento original y fechas intactos. |
| B con importe, revisión, instante o causación alterados | Conflicto contra B, incluso tras reinicio; ningún cambio confirmado. |

La igualdad técnica compara documento normalizado completo; la equivalencia empresarial sigue en `combinar`. No comparar bytes de transporte ni guardar solo el ID o el primer fragmento de la vista. Un fallo al confirmar B también debe revertir su entrada aunque no se haya modificado la vista.

## Metadatos y rollback local

Usar el reloj de aplicación ya inyectado. `primera_recepcion_en` se fija al crear la primera vista aceptada y permanece estable. `proyectada_en` se actualiza solo al incorporar un fragmento que cambia la proyección. Duplicados técnicos y empresariales no modifican ninguna fecha. Conservar por separado las fechas de cada fuente.

Vista, fragmentos, asociación de petición, metadatos e inbox se confirman o revierten juntos. Rollback descarta la operación local de Seguimiento; no compensa ni deshace acciones de Orquestación o Cotizaciones. No es una Saga.

Comparar ambos órdenes de llegada por contenido empresarial y completitud. No exigir igualdad de fechas locales entre corridas, ni de procedencia cuando distintos IDs equivalentes pueden ser los primeros aceptados. Para mensajes contradictorios, conservar el ganador confirmado y rechazar el otro; no imponer cuál debe ganar una carrera.

## Entorno, migraciones y composición

Añadir Alembic a dependencias y resolver el lockfile. Configurar `alembic.ini`, `migraciones/env.py` y metadata con vista e inbox. La migración desde vacío crea tablas, nulabilidad, restricciones e índices coherentes con el ORM. No ejecutar creación de tablas o migraciones al importar módulos ni como efecto oculto de bootstrap.

Definir `docker-compose.yaml` con servicio `postgres`, volumen y healthcheck propios. PostgreSQL 17.6 es la referencia ya usada por Entrada, no una afirmación de versión más reciente; registrar la imagen efectivamente probada. Elegir un puerto disponible para Seguimiento durante la implementación y documentarlo con el DSN de desarrollo. Conservar `SEGUIMIENTO_DATABASE_URL` y añadir `SEGUIMIENTO_TEST_DATABASE_URL`, sin reutilizar variables `PARTNER_*`.

El fixture de integración crea una BD efímera propia, aplica migraciones y la elimina al terminar; aísla datos entre pruebas. Solo elimina recursos creados por el fixture. Si PostgreSQL no está disponible, fallar con diagnóstico y comando de arranque: no sustituirlo por SQLite ni esconderlo mediante skips. La suite unitaria sigue sin depender de infraestructura.

La composición SQL reutiliza `create_database` y `componer_seguimiento`, con factoría de UoW y reloj inyectados. API/importaciones permanecen aislables y la persistencia funciona sin broker. Probar el wheel instalado fuera del árbol fuente con los nuevos componentes.

## Trabajo y pruebas obligatorias

1. Red: escribir pruebas significativas para serialización, contrato UoW y persistencia antes de implementar adaptadores.
2. Green: implementar migración, mapeadores, repositorio e inbox/UoW mínimos; después proteger carreras con bloqueo y reintentos completos.
3. Refactorizar en verde manteniendo reglas en dominio y SQL en infraestructura. Conservar el seedwork existente y añadir solo piezas usadas.
4. Ejecutar los handlers reales sobre PostgreSQL mediante bootstrap. Observar efectos confirmados desde otra UoW/transacción.
5. Actualizar README y registrar evidencia en `docs/evidencias/04-postgresql-vista-inbox.md`, incluidos entorno, pruebas rojas, resultados y límites.

| Prueba | Resultado obligatorio |
|---|---|
| Migración desde vacío y comparación con metadata | Tablas, columnas, índices y restricciones coinciden; no se permiten vistas sin fragmentos. |
| Round-trip de las cinco formas válidas | Creación, propuesta, rechazo y cada resultado combinado con creación conservan datos y propiedades derivadas. |
| Tipos y procedencia | UUID, nulos, importe entero exacto, fechas UTC, versiones y revisión compatible preservados. |
| Creación/resultado en ambos órdenes | Completar sin retroceso; categoría/red e identidades coherentes; conservar resultado. |
| Dos sesiones parten de ausencia | Una vista, dos fragmentos, dos inbox y metadatos completos después del reintento. Cubrir propuesta y rechazo. |
| Carrera sobre vista parcial existente | Bloqueo previo a combinar; sin actualizaciones perdidas ni sustitución del primer fragmento equivalente. |
| Mismo ID simultáneo | Una entrada si es idéntico; conflicto si difiere, incluso entre trabajos o tipos. |
| IDs distintos equivalentes y A/B/B alterado | Una entrada por ID aceptado; documentos históricos comparables; vista y fechas originales. |
| Petición ligada a otro trabajo, secuencial y concurrente | Una asociación; `ConflictoFragmentos` para el perdedor y ningún inbox suyo confirmado. |
| Propuesta y rechazo contradictorios, también concurrentes | Uno aceptado; el otro falla sin sobrescritura ni inbox confirmado. |
| Fallos tras inbox, vista, metadatos y durante confirmación | Estado previo intacto, Session cerrada y reintento válido posible. Incluir rama que solo escribe inbox. |
| Salida sin confirmar y reversión explícita | Sin cambios visibles desde otra UoW; petición del intento fallido no queda reservada. |
| Reintentos y agotamiento | Máximo tres intentos, UoW nuevas, fragmento estable, error propagado al agotar; no reintentar contradicciones. |
| Fechas locales | Primera recepción estable; proyección cambia solo con nuevo fragmento; fallos no filtran fechas. |
| Reinicio de proceso | Un proceso confirma parcial; otro, sin vaciar BD, la lee, completa y reconoce mensajes previos. Reabrir solo Session no basta. |
| Composición y aislamiento | Ambos handlers usan adaptadores SQL; dominio/aplicación sin frameworks, persistencia sin Pulsar, sesiones independientes. |

Usar barreras/eventos con timeout para forzar carreras, sin sleeps arbitrarios. No exigir en una barrera que ambos participantes hayan adquirido el mismo bloqueo exclusivo. En las pruebas negativas observar también conteo/contenido del inbox, metadatos y asociación de petición; una sola fila de vista no acredita atomicidad.

## Verificación y cierre

Los siguientes comandos son el procedimiento previsto para ejecutar **después de crear la configuración y migraciones de este incremento**, desde la raíz de Seguimiento y con las variables documentadas exportadas:

```bash
uv sync --locked
docker compose -f docker-compose.yaml up -d --wait postgres
uv run --locked alembic upgrade head
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts migraciones
uv run --locked python scripts/verify_distribution.py
git diff --check
```

La suite utiliza `SEGUIMIENTO_TEST_DATABASE_URL` y sus bases efímeras; la migración manual usa `SEGUIMIENTO_DATABASE_URL`. Concretar DSN/puerto y comprobar estos comandos durante la implementación; no declararlos ejecutados por estar escritos aquí. Para trabajo unitario aislado puede seleccionarse `tests/unitarias tests/api`, pero ese resultado no cierra 04.

Cerrar cuando las pruebas PostgreSQL, aislamiento, lint, formato, tipos y distribución pasen y la evidencia demuestre atomicidad, carreras y reinicio real. Exigir una entrada por mensaje aceptado y cero marcas confirmadas sin efecto o duplicado reconocido. No heredar conteos de 03 ni presentar los dobles como evidencia de durabilidad.

El cierre local usa casos de uso y PostgreSQL. Broker, ACK e interoperabilidad real quedan para 05/07; GET y filtro de duración para 06. La dependencia adelantada de GET en el plan 05 se mantiene como observación documental pendiente de ese plan, sin convertirla en requisito de 04.

Implementación terminada: 242 pruebas aprobadas, incluidas 51 PostgreSQL, lint/formato, tipos y wheel instalado fuera del árbol fuente. El entorno local usa PostgreSQL 17.6 en 55435; el fixture elimina únicamente sus bases efímeras. La evidencia registra comandos y límites. Consumidores/ACK y consultas HTTP siguen pendientes de 05/06. Sin commit ni push.

Reorganización posterior aprobada: la responsabilidad técnica común determina la ubicación en seedwork, aunque exista un único módulo. El contrato transaccional, base SQL, errores, reintentos y serialización básica están allí; metadatos, formato de fragmentos, repositorio y restricciones concretas permanecen en Seguimiento. Las pruebas verifican que el seedwork no importa módulos de negocio.
