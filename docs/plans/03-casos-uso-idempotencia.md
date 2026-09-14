# 03 — Proyectar hechos con idempotencia

Estado: implementado y verificado localmente. [Evidencia y límites](../evidencias/03-casos-uso-idempotencia.md). Ajustes H1–H6 de la [auditoría](auditoria-03-casos-uso-idempotencia.md) incorporados. Servicio: seguimiento. Ver [modelo y secuencia](README.md), [base común](comun/02-base-de-implementacion.md) y [contratos](comun/01-contratos-y-datos.md).

Dependencia local: [02](02-modelo-vista-seedwork.md).

## Objetivo y alcance

Aplicar creación y resultado de cotización al modelo de seguimiento mediante casos de uso y una unidad de trabajo (UoW), comprobados con dobles en memoria. Conservar fragmentos, vista, metadatos locales e inbox de forma atómica dentro de la operación simulada.

`VistaSeguimiento` permanece en `dominio/vistas.py` y `combinar` en `dominio/servicios.py`. Los handlers coordinan los puertos y usan esas reglas; no las duplican ni trasladan a infraestructura. Seguimiento describe hechos recibidos y no confirma que Orquestación haya aplicado ya el resultado.

Este incremento no incorpora Saga, outbox, publicador, bus interno ni consultas a productores. PostgreSQL y concurrencia real corresponden a 04; consumidores, Avro y ACK a 05; consultas HTTP y duración v2 a 06.

## Organización y contratos mínimos

Rutas relativas a `src/seguimiento_trabajos/`:

| Archivo | Responsabilidad |
|---|---|
| `modulos/seguimiento/dominio/repositorios.py` | Puerto específico para obtener/guardar `VistaSeguimiento` y garantizar una única asociación de petición a trabajo. |
| `modulos/seguimiento/aplicacion/unidad_trabajo.py` | Contexto transaccional, acceso al repositorio, preparación/comparación de inbox, metadatos locales, confirmación y reversión. |
| `modulos/seguimiento/aplicacion/handlers/proyectar_creacion.py` | Coordinar recepción de creación y combinación con la vista disponible. |
| `modulos/seguimiento/aplicacion/handlers/proyectar_resultado.py` | Coordinar recepción de propuesta o rechazo con el mismo flujo de proyección. |
| `modulos/seguimiento/aplicacion/handlers/proyectar_fragmento.py` | Secuencia transaccional compartida por los dos handlers, con identidad lógica de inbox única. |
| `modulos/seguimiento/aplicacion/metadatos.py` | Fechas locales inmutables normalizadas a UTC, separadas del modelo de dominio. |
| `modulos/seguimiento/aplicacion/excepciones.py` | `ConflictoMensaje` para reutilización contradictoria de un ID en inbox. |
| `seedwork/aplicacion/reloj.py` | Puerto de reloj utilizado por los dos handlers para las fechas locales. |
| `config/bootstrap.py` | Funciones de composición con factoría de UoW y reloj inyectados; sin conexiones ni reglas de negocio. |
| `tests/unitarias/aplicacion/dobles/` | Repositorio, inbox, reloj y UoW con almacén confirmado y estado provisional aislado. |

El repositorio devuelve ausencia cuando no existe vista. Al guardar debe rechazar una petición asociada a otro trabajo; el doble puede resolverlo con índice por petición o búsqueda equivalente. No exponer un CRUD genérico. El puerto recibe y devuelve tipos propios; no conoce SQL, Record Avro ni metadatos de transporte.

La UoW expone el repositorio y una operación `preparar_entrada` que recibe consumidor lógico y fragmento normalizado: devuelve verdadero para una entrada nueva provisional, falso para un duplicado idéntico y lanza conflicto ante contenido diferente. No requiere `EventoDominio` ni `registrar_salida` de Entrada. Una factoría crea una UoW independiente por invocación, con contexto, `confirmar` y `revertir`; salir sin confirmar descarta el estado provisional.

Los metadatos de coordinación se gestionan mediante operaciones propias de la UoW, dentro de la misma transacción, sin añadir fechas de recepción al dominio. En 04 estas operaciones delegan la E/S en repositorios y pueden actualizar la misma fila SQL que contiene los fragmentos. No exigen tablas o escrituras separadas.

Los handlers reciben directamente `DatosCreacion` y `DatosResultadoCotizacion`, respectivamente. Las firmas tipadas declaran el fragmento esperado; no se repite un `isinstance` defensivo en los handlers. Los constructores del dominio validan los datos y el adaptador de 05 traducirá y validará las entradas externas antes de invocarlos. No hay envoltorios `ProyectarCreacion`/`ProyectarResultado` ni archivo `aplicacion/comandos.py`: no aportaban información adicional. Los handlers retornan `None` al terminar correctamente y propagan los errores. Un duplicado coherente también es procesamiento exitoso. En 05 el adaptador distingue ese retorno exitoso de una excepción para decidir el ACK; aquí no se confirma ningún mensaje al broker.

Conservar el seedwork existente y añadir solo abstracciones usadas. El doble de reloj basta para 03; no conectar el procesamiento operativo al lifespan hasta 05. Ampliar `config/bootstrap.py` cuando lleguen adaptadores reales, sin crear un ensamblaje paralelo.

## Secuencia de una operación

1. Recibir directamente el fragmento propio validado indicado por la firma del handler. La traducción Avro corresponde al adaptador de 05.
2. Abrir una nueva UoW y preparar/comparar la entrada inbox antes de depender de la vista de un trabajo concreto.
3. Si el mensaje ya está confirmado e idéntico, terminar sin escrituras. Si su contenido difiere, propagar conflicto.
4. Obtener la vista por `id_trabajo` y usar `combinar` para validar identidades, coherencia y equivalencia empresarial.
5. Si la proyección cambia, guardar la vista con sus fragmentos, comprobar la asociación única de petición y actualizar sus metadatos locales.
6. Confirmar en una sola operación el estado provisional. Si el mensaje tiene ID nuevo pero el hecho es equivalente, confirmar únicamente su entrada inbox; la vista, sus fragmentos y sus fechas permanecen iguales.

No realizar GET al productor cuando falta creación. Un resultado primero crea una vista parcial; la creación posterior la completa sin reiniciar el estado ni reemplazar el resultado.

## Inbox: reconocer cada mensaje aceptado

Usar `(consumidor_logico, event_id)` con identidad lógica estable `seguimiento.proyeccion`, compartida por ambos handlers y todas las réplicas. Los tres nombres de suscripción de Pulsar de 05 permanecen independientes de esta clave. No añadir réplica, tipo de evento ni revisión del lector al consumidor lógico: el mismo ID reutilizado entre tipos o trabajos debe detectarse dentro de este efecto.

Cada entrada aceptada conserva todos los datos normalizados conocidos por el lector: identidad, contenido empresarial y procedencia, incluidos tipo, revisión, instante, correlación y causación. En 03 pueden conservarse los tipos propios inmutables; la representación serializada llega en 04. No guardar solo el ID, la vista resultante ni únicamente la procedencia del primer fragmento.

| Recepción | Efecto esperado |
|---|---|
| A contiene una cotización válida | Guardar resultado y registrar A. |
| A vuelve idéntico | Ninguna escritura ni segundo efecto. |
| B tiene otro ID y representa la misma cotización | Registrar B; conservar vista y procedencia de A. |
| B reaparece con importe, instante o causación diferentes | Conflicto contra el contenido registrado de B; conservar el estado anterior. |

Esto es un inbox con contenido por mensaje aceptado, no un historial de versiones de la vista ni un event store. No incluye replay general, archivo de mensajes rechazados ni reconstrucción de proyecciones.

Separar igualdad técnica de equivalencia empresarial: mismo ID exige datos y procedencia iguales tras normalización; nuevo ID compara el hecho mediante `combinar` y conserva el fragmento original. No comparar bytes Avro ni inventar conocimiento de campos ignorados por un lector antiguo. CotizacionRegistrada admite las revisiones compatibles del plan 02; no imponer revisión 1 ni borrar la revisión de origen. La evolución binaria se prueba en 05/07.

Los productores deben conservar sus IDs al reenviar. Aceptar el mismo hecho con otro ID es una defensa adicional del consumidor, no una autorización para regenerar resultados o recotizar.

## Identidad de trabajo y petición

Una petición corresponde a un único trabajo y esta POC admite una sola petición por trabajo. Si ya existe `Trabajo A → Petición P`, intentar guardar `Trabajo B → Petición P` produce conflicto, aunque B todavía no tenga vista y el mensaje tenga un ID nuevo.

Esta verificación pertenece al contrato del repositorio y se comprueba con el doble en 03; 04 la materializa con PK por trabajo y UNIQUE por petición, además de pruebas de concurrencia. Si falla, tampoco se confirma el inbox del mensaje contradictorio. No añadir nuevas restricciones empresariales sobre otros campos por inferencia.

Dentro de la vista, los cuatro IDs comunes deben coincidir. Creación y propuesta deben coincidir también en categoría y red. Rechazo y propuesta son excluyentes para una petición. Estas reglas siguen centralizadas en el dominio de 02; no decidir por timestamp ni comparar versiones de propietarios distintos.

Correlación refiere la solicitud. Las causaciones de creación y resultado pueden ser distintas: Seguimiento conserva ambas y no exige una cadena causal que los contratos recibidos no permiten reconstruir.

## Rollback local y fechas

Rollback significa descartar los cambios no confirmados de la operación de Seguimiento: inbox, fragmentos, vista, índice de petición y metadatos. No deshace acciones de Orquestación o Cotizaciones ni ejecuta compensaciones; no es una Saga.

El doble mantiene un estado provisional separado del almacén confirmado. Preparar inbox no lo publica todavía. Un fallo de guardado o confirmación, una excepción de dominio, una reversión explícita o salir sin confirmar dejan intacto el estado confirmado. Después se puede reintentar con una nueva UoW. Las referencias entregadas por el doble no permiten modificar por fuera el estado confirmado.

Usar el reloj inyectado para obtener fechas locales UTC:

- Primera recepción aceptada: se fija al crear la vista y permanece estable al llegar el segundo fragmento o un duplicado.
- `proyectada_en`: se fija al crear la vista y se actualiza al aceptar un fragmento que cambia la proyección.
- Duplicados técnicos y empresariales no modifican ninguna de esas fechas.
- Un fallo descarta las fechas provisionales junto con el resto de la operación.

Las fechas de origen permanecen en los fragmentos sin alteración. Las fechas locales no forman parte de la igualdad empresarial entre ejecuciones ni seleccionan el ganador. El orden por primera recepción e ID de 06 debe usar esta semántica.

## Trabajo y matriz de pruebas

1. Reutilizar fixtures propios de 02 y el comportamiento de UoW/inbox de Entrada como referencia conceptual. No importar paquetes de productores ni copiar su proyector de snapshots o su outbox.
2. Red: escribir pruebas que fallen significativamente por los casos de uso y contratos pendientes antes de implementar.
3. Green: implementar puertos, handlers y dobles mínimos, recibiendo los fragmentos propios existentes. Refactorizar en verde manteniendo las reglas de combinación en dominio.
4. Probar composición e importación aislada; ampliar el script de distribución con los componentes públicos que existan en 03.
5. Actualizar README y registrar evidencia real en `docs/evidencias/03-casos-uso-idempotencia.md`.

Casos obligatorios:

- Creación sola, propuesta sola y rechazo solo dejan el contenido esperado visible desde una nueva UoW del doble; ambos órdenes completan la vista sin regresión.
- Duplicados idénticos y equivalentes con ID nuevo intercalados antes/después de completar: una vista, fragmentos originales y una entrada por ID aceptado.
- Secuencia A/B/B alterado: detectar individualmente cambios de datos empresariales y procedencia del mensaje B. Reutilizar un ID entre trabajos o tipos también falla.
- Petición ya asociada a A no puede guardarse para B, con A parcial o completo; conservar A y no confirmar el inbox de B.
- Conflictos de IDs, categoría/red, contenido o resultados opuestos mantienen el estado previo. Cubrir los dos resultados y ambos órdenes de llegada.
- Fallo controlado durante preparación de inbox, guardado y confirmación; excepción de dominio, reversión explícita y salida sin confirmar. Ningún caso filtra cambios; una nueva invocación válida puede reintentar y confirmar un único efecto.
- ID nuevo equivalente confirma su inbox aun sin guardar nuevamente la vista. Misma entrada ya confirmada termina correctamente sin escrituras.
- Reloj falso: primera recepción estable; proyección actualizada solo al cambiar fragmentos; replay no cambia fechas y fallo no publica fechas provisionales.
- Dos invocaciones usan UoW diferentes. Bootstrap ensambla dobles sin conectar recursos; otra UoW observa solo lo confirmado.
- Importar dominio/aplicación en un intérprete limpio con FastAPI, SQLAlchemy, psycopg, Pulsar y paquetes de productores bloqueados. Ejecutar handlers sin red ni llamadas HTTP; mantener las pruebas de aislamiento de 01/02.

No usar el doble para afirmar recuperación tras reinicio de proceso, carreras SQL o entrega durable. En 04 se prueban con infraestructura real las garantías contractuales aquí simuladas.

## Verificación y cierre

Desde la raíz de Seguimiento:

```bash
uv run --locked pytest tests -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy src tests scripts
uv run --locked python scripts/verify_distribution.py
```

No incluir `migraciones` antes de crearla en 04. Registrar test rojo, comandos, resultados observados y límites; no heredar el conteo de pruebas de incrementos anteriores. Comprobar el wheel instalado fuera del árbol fuente con los nuevos componentes.

Cerrar cuando los casos de uso, identidad, metadatos, rollback y composición estén verificados con dobles y las verificaciones locales pasen. La evidencia demuestra estado confirmado visible desde otra UoW en memoria, no durabilidad real. Inspeccionar la vista mediante los puertos/dobles no implica implementar consultas HTTP, filtros o paginación de 06.

Implementación terminada y verificada con dobles; persistencia durable, concurrencia SQL y transporte siguen pendientes de 04/05. El plan no autoriza commit ni push.
