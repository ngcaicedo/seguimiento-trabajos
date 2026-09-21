from typing import Any

import pulsar
from pulsar.schema import AvroSchema

from seguimiento_trabajos.modulos.seguimiento.infraestructura.esquemas.v1.saga import saga_schemas
from seguimiento_trabajos.seedwork.infraestructura.ciclos import AccionError, FalloPaso
from seguimiento_trabajos.seedwork.infraestructura.serializacion import Documento


class TrackingPublisher:
    def __init__(self, url: str, topics: dict[str, str]) -> None:
        self.url = url
        self.topics = topics
        self.client: Any = None
        self.producers: dict[str, Any] = {}

    def check_connection(self) -> None:
        try:
            if self.client is None:
                self.client = pulsar.Client(
                    self.url, operation_timeout_seconds=1, connection_timeout_ms=1000
                )
                schemas = saga_schemas()
                for kind, topic in self.topics.items():
                    self.producers[kind] = self.client.create_producer(
                        topic,
                        schema=AvroSchema(schemas[kind]),
                        send_timeout_millis=1000,
                        batching_enabled=False,
                        block_if_queue_full=False,
                    )
            if not all(producer.is_connected() for producer in self.producers.values()):
                raise ConnectionError("Publicador desconectado")
        except Exception as error:
            self._raise_failure(error)

    def publish(self, kind: str, payload: Documento) -> None:
        self.check_connection()
        record = saga_schemas()[kind](**payload)
        try:
            self.producers[kind].send(record, partition_key=str(payload["id_trabajo"]))
        except Exception as error:
            self._raise_failure(error)

    def _raise_failure(self, error: Exception) -> None:
        self.close()
        transient = isinstance(
            error,
            (
                ConnectionError,
                OSError,
                pulsar.Timeout,
                pulsar.ConnectError,
                pulsar.NotConnected,
                pulsar.AlreadyClosed,
                pulsar.LookupError,
                pulsar.ReadError,
                pulsar.ServiceUnitNotReady,
                pulsar.BrokerPersistenceError,
                pulsar.ProducerQueueIsFull,
            ),
        )
        raise FalloPaso(
            AccionError.REINTENTAR if transient else AccionError.PAUSAR,
            {"motivo": type(error).__name__},
        ) from error

    def close(self) -> None:
        client = self.client
        self.client = None
        self.producers = {}
        if client is not None:
            try:
                client.close()
            except pulsar.AlreadyClosed:
                pass
