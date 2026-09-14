# 02 — Vista de seguimiento y reglas de combinación

Estado: implementado y verificado localmente. [Evidencia y límites](../evidencias/02-modelo-vista-seedwork.md). Ajustes H1–H5 de la [auditoría](auditoria-02-modelo-vista-seedwork.md) incorporados. Servicio: seguimiento. Ver [modelo y secuencia](README.md), [base común](comun/02-base-de-implementacion.md) y [contratos](comun/01-contratos-y-datos.md).

Dependencia local: [01](01-base-tecnologica.md).

Reorganización aplicada y verificada: `VistaSeguimiento` reside en `dominio/vistas.py`; combinación, pruebas y distribución utilizan esa ubicación. La evidencia registra la verificación posterior, sin cambios de comportamiento.

## Objetivo y alcance

Definir y probar un modelo local inmutable que combina creación y resultado de cotización, independientemente del orden de llegada. Consume datos traducidos de `TrabajoCreado.v1`, `CotizacionRegistrada.v1` y `CotizacionRechazada.v1`; no importa clases de eventos, Trabajo, Cotizacion ni ORM de otros servicios.

Seguimiento describe hechos recibidos, no el estado confirmado de Orquestación. La POC admite una petición por trabajo, sin recotización; propuesta y rechazo son resultados alternativos. La carpeta `dominio` agrupa las reglas de este modelo local, sin introducir otro dominio empresarial.

Este incremento entrega tipos, validaciones y funciones puras. Casos de uso e inbox con dobles corresponden a 03; persistencia y concurrencia a 04; consumidores y Avro a 05; API y duración estimada v2 a 06. No añadir outbox, publicador, bus interno, Saga ni un segundo proyector.

## Organización

Rutas de código relativas a `src/seguimiento_trabajos/`:

| Archivo | Responsabilidad |
|---|---|
| `modulos/seguimiento/dominio/objetos_valor.py` | Identidades, procedencia, `DatosCreacion`, `DatosResultadoCotizacion` y enumeraciones. Validación de cada fragmento; resultado con variantes excluyentes de propuesta/rechazo. |
| `modulos/seguimiento/dominio/vistas.py` | `VistaSeguimiento`: fragmentos, invariantes de coexistencia y propiedades derivadas de estado, completitud y datos disponibles. |
| `modulos/seguimiento/dominio/servicios.py` | Combinación pura y reconocimiento de duplicados; construye vistas que validan la coherencia entre fragmentos. |
| `modulos/seguimiento/dominio/excepciones.py` | `ConflictoFragmentos` para hechos incompatibles. |
| `seedwork/dominio/validaciones.py` | Validaciones compartidas de UUID, enteros positivos, texto y fechas UTC, usadas por identidad, procedencia y fragmentos. |
| `seedwork/dominio/excepciones.py` | DatosInvalidos para validaciones compartidas y específicas; ConflictoFragmentos permanece en el módulo. |
| `tests/unitarias/dominio/` | Fixtures propios, invariantes, combinación y aislamiento. |

No copiar el seedwork completo de Entrada ni crear clases vacías. Los puertos de repositorio se concretan en 03 cuando los casos de uso los requieran; UoW pertenece a aplicación. No hace falta una entidad empresarial con eventos pendientes para representar esta vista.

### Modelo local y representación SQL

`VistaSeguimiento` permanece en dominio porque expresa el modelo local de seguimiento y las reglas sobre qué hechos pueden coexistir. Sus propiedades describen ese modelo, independientemente de cómo se consulte o almacene. No es dueño del Trabajo de Orquestación ni representa una tabla SQL.

En 04, la representación SQL se implementa en `infraestructura/orm.py`, según su plan; los mapeadores convierten entre ella y el modelo local. No mover `VistaSeguimiento` a infraestructura ni duplicar sus reglas en el ORM. Tampoco trasladar la combinación a aplicación: los casos de uso de 03 coordinan repositorios/inbox y utilizan esta operación de dominio.

La dependencia queda `servicios.py → vistas.py → objetos_valor.py`, con excepciones y seedwork como dependencias compartidas. `objetos_valor.py` no importa ni reexporta la vista; así se evita un ciclo y cada tipo tiene una ubicación explícita.

### Trabajo de reorganización

1. Mover únicamente `VistaSeguimiento` y sus propiedades a `dominio/vistas.py`, conservando invariantes y comportamiento.
2. Actualizar imports de combinación, fixtures, pruebas de modelo/aislamiento y script de distribución. Conservar el docstring en español de `combinar`.
3. Actualizar README y evidencia con la organización final. Las referencias históricas de la auditoría se mantienen identificadas como antecedentes.
4. Ejecutar pruebas, lint, formato, tipos y distribución indicados al cierre. Verificar que los consumidores de la clase importan desde `dominio/vistas.py` y que dominio sigue independiente de infraestructura.

Este cambio reorganiza código existente; no añade otra vista, otra capa de proyección ni nuevos comportamientos.

## Modelo e invariantes

La vista contiene `id_trabajo`, `id_solicitud`, `id_partner`, `id_peticion` y al menos un fragmento. Ausencia total se representa como ausencia de vista, no como `VistaSeguimiento` vacía. Estado y `creacion_recibida` se derivan de los fragmentos; si se reconstruyen desde valores almacenados, se comprueba su coherencia.

| Fragmentos | Estado | `creacion_recibida` |
|---|---|---|
| Solo creación | `PENDIENTE_COTIZACION` | true |
| Solo propuesta | `COTIZACION_REGISTRADA` | false |
| Solo rechazo | `COTIZACION_RECHAZADA` | false |
| Creación + propuesta | `COTIZACION_REGISTRADA` | true |
| Creación + rechazo | `COTIZACION_RECHAZADA` | true |

Cada fragmento conserva datos del hecho y procedencia: tipo, ID de evento, revisión, instante, correlación y causación originales. Los campos del contrato común se representan con tipos propios; no almacenar objetos de transporte ni diccionarios mutables expuestos como modelo.

- Validar UUID no nulos, textos no vacíos, enums permitidos y fechas con zona, normalizadas a UTC. Correlación corresponde a `id_solicitud`.
- Creación conserva referencia, categoría, tipo de solicitud, red, política/versionado y `creado_en`; exige estado inicial y `version_trabajo=1` según el contrato vigente.
- Ambos resultados conservan versiones de catálogo y cotización. La versión de catálogo es positiva y `version_cotizacion=1` en este recorte.
- Propuesta requiere cotización, proveedor, categoría, red, importe entero positivo en unidades menores y moneda COP; no tiene motivo de rechazo.
- Rechazo requiere `SIN_OFERTA_PARA_CATEGORIA` o `SIN_PROVEEDOR_EN_RED`; no tiene proveedor, precio ni cotización ficticios.
- Los enteros no aceptan booleanos. Versiones de política y revisión cumplen sus contratos; no se comparan versiones de Trabajo y Cotizaciones ni se impone orden temporal entre propietarios.

Construcción y reconstrucción aplican las mismas invariantes. Reconstruir conserva datos y procedencia, sin producir eventos, nuevos IDs ni fechas actuales. Los tipos anidados también son inmutables; fallar una validación o combinación no altera la entrada.

## Coherencia y datos parciales

Al combinar, los cuatro IDs comunes deben coincidir. Si hay creación y propuesta, también deben coincidir `categoria` y `tipo_red`. Mismos IDs con categoría o red distintas son conflicto en cualquiera de los órdenes: conservar los fragmentos previos y señalar la contradicción. Seguimiento no decide qué red es correcta ni reevalúa la política o el catálogo.

Una propuesta parcial ya aporta categoría y red; puede mostrarlas aunque falte creación. Referencia externa, fecha de creación, tipo de solicitud y política permanecen desconocidos hasta recibirla. Un rechazo parcial no aporta categoría ni red: se mantienen desconocidas hasta recibir creación. Los campos ausentes son null, nunca valores inventados.

Creación tardía completa únicamente los datos faltantes y conserva el resultado. No reinicia el estado a pendiente ni sobrescribe datos contradictorios. No consultar otros servicios para completar la vista.

## Duplicados, conflictos y procedencia

Separar equivalencia empresarial y comparación técnica:

| Dato | Mismo ID de mensaje | Nuevo ID para el mismo hecho |
|---|---|---|
| Tipo e identidades de trabajo/solicitud/partner/petición | Deben coincidir | Deben coincidir |
| Datos empresariales y versiones de su fuente | Deben coincidir tras normalización | Deben coincidir; un nuevo ID no permite cambiar importe, proveedor, motivo, política, etc. |
| `event_id` | Identifica el mensaje | No determina equivalencia empresarial; conservar el del fragmento aceptado |
| `instante` y `causacion` | Deben coincidir tras normalización | No seleccionan ganador ni reemplazan procedencia; conservar los originales |
| `correlacion` | Debe coincidir y referir la solicitud | Debe coincidir y referir la solicitud |
| Revisión de contrato | Debe coincidir; un mismo mensaje no cambia de revisión | Es procedencia, no versión empresarial ni criterio de ganador. La equivalencia compara datos empresariales conocidos por el lector, no exige igual revisión compatible |

El contenido empresarial incluye todos los datos del fragmento: en creación también `creado_en`; en resultado también las versiones de catálogo/cotización. La normalización no cambia significado ni ignora campos conocidos para ocultar un conflicto.

Duplicado técnico idéntico es no-op. Nuevo ID con mismo tipo, identidades y contenido empresarial es no-op y conserva el fragmento original. Mismo hecho con datos empresariales distintos es conflicto. Dos resultados opuestos también son conflicto. No exigir igualdad de causación entre creación y resultado: referencian mensajes diferentes según el contrato.

Los productores previstos conservan ID, instante y contenido de cada salida en sus reintentos. Una petición repetida, incluso con otro `command_id`, no crea otro evento de resultado en Cotizaciones. El caso de nuevo `event_id` para un hecho equivalente es una defensa del consumidor exigida por el contrato común, no una instrucción para regenerar mensajes ni una recotización válida. La tolerancia de procedencia en ese caso no permite a los productores cambiar la causación original.

Seguimiento conserva la causación, pero no puede verificar toda la cadena causal con sus dos fragmentos: TrabajoCreado referencia el evento de Entrada; el resultado referencia el comando de cotización, cuyo `command_id` no viene en TrabajoCreado. Valida formato y coherencia observable mediante los cuatro IDs comunes; no inventa ese enlace ni consulta Orquestación para reconstruirlo.

02 prueba estas comparaciones con los fragmentos disponibles. La búsqueda histórica por `(consumidor_logico, event_id)` y la escritura de inbox se implementan en 03/04; el modelo puro no acredita deduplicación durable ni detecta por sí solo IDs de otros trabajos no cargados.

Los fixtures iniciales usan revisión 1, pero el modelo no impone `version_contrato == 1` para CotizacionRegistrada. Desde 05 su lector v1 debe aceptar las revisiones compatibles previstas, conservar la revisión de origen y traducir los campos conocidos sin incorporar duración. La capacidad de usar duración y normalizar ausencia/null llega en 06; la prueba binaria de compatibilidad corresponde a 05/07. TrabajoCreado y CotizacionRechazada permanecen en revisión 1. La evolución no autoriza modificar un hecho existente ni enriquecer históricos con el mismo ID.

## Convergencia

Ambos órdenes deben producir el mismo contenido proyectado, estado y completitud. Con los mismos fragmentos se preserva además la misma procedencia de origen. Duplicados intercalados no cambian el contenido ni hacen retroceder la vista.

Las fechas locales de primera recepción/proyección pertenecen a coordinación y persistencia, con reloj explícito desde los incrementos correspondientes. No forman parte de la igualdad empresarial entre ejecuciones distintas. Si dos copias empresariales equivalentes tienen IDs diferentes, se conserva la procedencia de la primera aceptada; no se exige que esa procedencia sea idéntica entre corridas con distinto orden.

La combinación no usa reloj global, timestamps como criterio de ganador ni una versión global. No copiar la actualización por snapshot de mayor `version_solicitud` del proyector de Entrada.

## Trabajo y pruebas

1. Crear fixtures propios trazables al contrato común v1, con identidades y fechas explícitas. Los contratos nuevos siguen pendientes de exportación y prueba por sus propietarios; no presentar estos fixtures como evidencia Avro.
2. Red: escribir los casos siguientes y registrar un fallo significativo antes de implementar el modelo.
3. Green: implementar los tipos y funciones puras mínimos. Refactorizar con las pruebas en verde.
4. Añadir importación del modelo y sus funciones en intérprete limpio, bloqueando FastAPI, SQLAlchemy, psycopg, Pulsar y paquetes de otros servicios. La prueba de red/lifespan de 01 permanece y no sustituye esta comprobación.
5. Ampliar la verificación de distribución para importar los nuevos tipos públicos desde el wheel instalado fuera del árbol fuente. Documentar modelo, estados y límites en README y resultados reales en `docs/evidencias/02-modelo-vista-seedwork.md`.

### Matriz obligatoria

- Construir y reconstruir los cinco estados válidos; rechazar vista vacía, estado/bandera incoherentes, resultado híbrido, campos requeridos ausentes y valores/tipos inválidos.
- Creación/propuesta y creación/rechazo convergen en ambos órdenes; probar datos disponibles y null en cada vista parcial.
- Alterar individualmente cada uno de los cuatro IDs; fallar sin mutar la vista previa.
- Categoría distinta y red distinta entre creación/propuesta fallan en ambos órdenes.
- Duplicado idéntico y nuevo ID con hecho equivalente no cambian contenido ni procedencia aceptada; intercalarlos antes y después de completar la vista.
- Misma creación alterando referencia o política, misma propuesta alterando importe o proveedor y mismo rechazo alterando motivo son conflictos. Probar también versiones empresariales distintas, sin tratar una mayor como autorización de reemplazo.
- Mismo ID con instante o causación alterados es conflicto técnico; nuevo ID con hecho empresarial equivalente conserva la procedencia previa.
- Datos propios de propuesta traducidos desde la revisión compatible 2 se aceptan sin exigir duración ni cambiar el significado de los campos v1; revisión de esquema y versión de cotización se validan por separado. Esta prueba pura no acredita Avro ni aceptación por el broker.
- Propuesta seguida de rechazo y rechazo seguido de propuesta fallan sin sobrescribir el resultado.
- Conservar instantes originales sin seleccionar ganador por tiempo; reconstruir no genera efectos ni valores nuevos.
- Comprobar inmutabilidad de la vista y sus fragmentos, y aislamiento de imports además de ausencia de red.

## Verificación y cierre

Ejecutar desde la raíz del servicio:

```bash
uv run --locked pytest tests/unitarias tests/api -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
git diff --check
```

Cerrar cuando la matriz funcional, aislamiento y empaquetado pasen y README/evidencia expliquen resultados realmente observados, incluidos Red → Green → Refactor. No heredar conteos de Entrada ni presentar verificaciones futuras como ejecutadas. Este incremento no acredita transacciones, concurrencia PostgreSQL, entrega Pulsar ni HTTP de negocio. No autoriza commit o push.
