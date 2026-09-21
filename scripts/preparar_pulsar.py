from seguimiento_trabajos.config.rutas import fuentes, reply_topics, saga_sources
from seguimiento_trabajos.config.settings import Settings


def preparar(settings: Settings) -> None:
    import pulsar
    from pulsar.schema import AvroSchema

    from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.eventos import (
        esquemas,
    )

    cliente = pulsar.Client(
        settings.pulsar_url, operation_timeout_seconds=2, connection_timeout_ms=1000
    )
    try:
        registros = esquemas()
        from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.saga import (
            saga_schemas,
        )

        for source in saga_sources(settings):
            registros[source.nombre] = saga_schemas()[source.tipo]
        for fuente in (*fuentes(settings), *saga_sources(settings)):
            schema = AvroSchema(registros[fuente.nombre])
            productor = cliente.create_producer(fuente.topico, schema=schema)
            productor.close()
            consumidor = cliente.subscribe(
                fuente.topico,
                fuente.suscripcion,
                schema=schema,
                initial_position=pulsar.InitialPosition.Earliest,
                consumer_type=pulsar.ConsumerType.Shared,
            )
            consumidor.close()
        for kind, topic in reply_topics(settings).items():
            producer = cliente.create_producer(topic, schema=AvroSchema(saga_schemas()[kind]))
            producer.close()
    finally:
        cliente.close()


if __name__ == "__main__":
    preparar(Settings.from_environment())
