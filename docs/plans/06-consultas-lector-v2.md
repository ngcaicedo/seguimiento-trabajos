# 06 — POC de consulta V1

Estado: implementado y verificado localmente. [Evidencia de cierre](../evidencias/06-consultas-v1.md). Alcance mínimo aprobado e incorporado desde la [auditoría](auditoria-06-consultas-lector-v2.md). Ver [modelo y secuencia](README.md). Dependencia local: [05](05-pulsar-lectores-v1.md), implementado con productores de contrato; integración con productores propietarios pendiente.

## Objetivo y alcance

Demostrar el recorrido **eventos V1 → proyección persistida → GET por ID**, usando la aplicación y los consumidores existentes.

Un único endpoint: `GET /seguimiento/trabajos/{id_trabajo}`. Sin listado, filtros, paginación, duración estimada, lector v2 ni migraciones de evolución. No requiere otra tabla, proyección, tópico o bus. La evolución de contratos queda fuera del cierre de esta POC.

## Implementación

1. Definir un puerto de lectura con `obtener` en `aplicacion/consultas.py`, un handler y una respuesta de consulta propia en aplicación. Mantener `VistaSeguimiento` y `combinar` en dominio; la respuesta no duplica sus reglas.
2. Implementar la lectura en una clase dentro de `infraestructura/repositorios.py`, sobre `VistaSeguimientoSQL`. Usar SELECT ordinario y sesión propia por consulta; no reutilizar la lectura con `FOR UPDATE` del proyector. Obtener contenido y metadatos de la misma fila y convertirlos antes de cerrar la sesión. Consultar no escribe fragmentos, inbox ni fechas.
3. Componer mediante bootstrap y registrar `api/seguimiento.py` en la factoría de la app actual. Reutilizar la base del lifespan y ejecutar la E/S SQL síncrona fuera del event loop. SQL permanece en infraestructura; no añadir una UoW de lectura ni fábricas genéricas.
4. Reutilizar seedwork, factoría de sesiones y consumidores de 05. Conservar health y su supervisión; el GET puede leer datos confirmados si la DB funciona aunque el consumo esté pausado. No consultar APIs ni bases de los productores para completar la respuesta.

## Respuesta HTTP

Una respuesta sencilla incluye:

- `id_trabajo`, `id_solicitud`, `id_partner`, `id_peticion`.
- `estado`, `creacion_recibida`.
- `referencia_externa`, `categoria`, `tipo_red`.
- `id_cotizacion`, `id_proveedor`, `importe_menor`, `moneda`, `motivo`.
- `proyectada_en`, tomada de los metadatos persistidos.

Usar los valores existentes del modelo. Datos desconocidos → null. Propuesta parcial ya conoce categoría/red; rechazo parcial no. Creación tardía completa los datos sin borrar el resultado. Conservar importe entero y unidad del contrato V1, sin convertir a float. No exponer el formato JSONB privado ni todas las revisiones y políticas internas.

| Respuesta | Significado |
|---|---|
| 200 | Existe una proyección, completa o parcial. |
| 404 | No hay fragmentos disponibles en Seguimiento; puede existir retraso de proyección. |
| 422 | ID inválido. |
| 503 | Base no configurada o indisponibilidad conocida de persistencia. |

No transformar errores inesperados en 404 ni en indisponibilidad genérica. `COTIZACION_REGISTRADA` describe el hecho recibido; no certifica que Orquestación ya lo haya aplicado.

## Pruebas y cierre

Aplicar Red → Green → Refactor con pruebas proporcionales al cambio:

1. Casos parametrizados de creación sola, propuesta sola, rechazo solo y combinaciones con creación; comprobar respuesta, nulos, ID ausente/inválido y DB no disponible.
2. Lectura real PostgreSQL desde sesión propia; consultar no cambia vista, inbox ni metadatos.
3. Recorrido Pulsar → consumidores → PostgreSQL → GET HTTP real, mostrando vista parcial y posterior completitud con propuesta y rechazo. Reutilizar fixtures y harness de 05 con esperas acotadas; no repetir su campaña de recuperación y apagado.

Documentar arranque y ejemplos de curl en README; usar el OpenAPI generado por la app. Registrar comandos, resultados y limitaciones en `docs/evidencias/06-consultas-v1.md`. Ejecutar tests, lint, formato, tipos y distribución mediante los comandos vigentes del proyecto. Las pruebas reales fallan si falta infraestructura.

Cerrar localmente con productores de contrato V1 identificados como tales. El intercambio con productores propietarios conserva su estado pendiente hasta contar con evidencia grupal. No implementar E3 para cerrar 06.
