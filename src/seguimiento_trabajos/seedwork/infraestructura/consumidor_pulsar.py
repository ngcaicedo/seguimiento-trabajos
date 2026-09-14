from collections.abc import Callable
from typing import Any

from seguimiento_trabajos.seedwork.infraestructura.ciclos import AccionError, FalloPaso


class ConsumidorPulsar:
    def __init__(
        self,
        url: str,
        topico: str,
        suscripcion: str,
        schema: Any,
        procesar: Callable[[Any], None],
        clasificar: Callable[[Exception], AccionError],
        *,
        crear_cliente: Callable[..., Any] | None = None,
        recepcion_ms: int = 500,
        reentrega_ms: int = 1000,
    ) -> None:
        if not topico.startswith("persistent://") or not suscripcion.strip():
            raise ValueError("Se requiere topico persistente y suscripcion")
        if not 1 <= recepcion_ms <= 1000 or reentrega_ms < 1000:
            raise ValueError("Limites de recepcion o reentrega invalidos")
        self.url = url
        self.topico = topico
        self.suscripcion = suscripcion
        self.schema = schema
        self.procesar = procesar
        self.clasificar = clasificar
        self.crear_cliente = crear_cliente
        self.recepcion_ms = recepcion_ms
        self.reentrega_ms = reentrega_ms
        self._cliente: Any = None
        self._consumidor: Any = None

    def abrir(self) -> None:
        if self._consumidor is not None:
            return
        import pulsar

        fabrica = self.crear_cliente or pulsar.Client
        self._cliente = fabrica(self.url, operation_timeout_seconds=1, connection_timeout_ms=1000)
        try:
            self._consumidor = self._cliente.subscribe(
                self.topico,
                self.suscripcion,
                schema=self.schema,
                consumer_type=pulsar.ConsumerType.Shared,
                initial_position=pulsar.InitialPosition.Earliest,
                receiver_queue_size=1,
                negative_ack_redelivery_delay_ms=self.reentrega_ms,
            )
        except Exception:
            self.cerrar()
            raise

    def _fallo(self, error: Exception, accion: AccionError, mensaje: Any = None) -> FalloPaso:
        diagnostico = {
            "topico": self.topico,
            "suscripcion": self.suscripcion,
            "motivo": type(getattr(error, "causa", error)).__name__,
        }
        if mensaje is not None:
            diagnostico["message_id"] = str(mensaje.message_id())
        identificador = getattr(error, "event_id", None)
        if isinstance(identificador, str):
            diagnostico["event_id"] = identificador
        return FalloPaso(accion, diagnostico)

    def procesar_siguiente(self) -> bool:
        import pulsar

        try:
            self.abrir()
            if not self._consumidor.is_connected():
                raise ConnectionError("Consumidor desconectado")
            mensaje = self._consumidor.receive(timeout_millis=self.recepcion_ms)
        except pulsar.Timeout:
            if self._consumidor is not None and self._consumidor.is_connected():
                return False
            self.cerrar()
            raise self._fallo(ConnectionError(), AccionError.REINTENTAR) from None
        except Exception as error:
            self.cerrar()
            transitorio = isinstance(
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
                ),
            )
            raise self._fallo(
                error, AccionError.REINTENTAR if transitorio else AccionError.PAUSAR
            ) from error
        try:
            self.procesar(mensaje)
        except Exception as error:
            accion = self.clasificar(error)
            if accion == AccionError.REINTENTAR:
                try:
                    self._consumidor.negative_acknowledge(mensaje)
                except Exception:
                    self.cerrar()
            raise self._fallo(error, accion, mensaje) from error
        try:
            self._consumidor.acknowledge(mensaje)
        except Exception as error:
            self.cerrar()
            raise self._fallo(error, AccionError.REINTENTAR, mensaje) from error
        return True

    def cerrar(self) -> None:
        cliente = self._cliente
        self._cliente = None
        self._consumidor = None
        if cliente is not None:
            import pulsar

            try:
                cliente.close()
            except pulsar.AlreadyClosed:
                pass
