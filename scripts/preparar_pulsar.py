from seguimiento_trabajos.config.rutas import fuentes
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
        for fuente in fuentes(settings):
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
    finally:
        cliente.close()


if __name__ == "__main__":
    preparar(Settings.from_environment())
