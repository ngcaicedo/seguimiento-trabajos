import logging
from collections.abc import Callable
from enum import StrEnum
from threading import Event, Lock, Thread
from typing import Any


class AccionError(StrEnum):
    REINTENTAR = "reintentar"
    PAUSAR = "pausar"


class FalloPaso(Exception):
    def __init__(self, accion: AccionError, diagnostico: dict[str, str]) -> None:
        super().__init__(diagnostico.get("motivo", "fallo"))
        self.accion = accion
        self.diagnostico = diagnostico


class Ciclo:
    def __init__(
        self,
        nombre: str,
        paso: Callable[[], bool],
        cerrar: Callable[[], None],
        pausa: float = 0.5,
    ) -> None:
        if pausa <= 0:
            raise ValueError("La pausa debe ser positiva")
        self.nombre = nombre
        self.paso = paso
        self.cerrar = cerrar
        self.pausa = pausa
        self.parada = Event()
        self._lock = Lock()
        self._estado = "iniciando"
        self._error_cierre: Exception | None = None
        self._diagnostico: dict[str, str] | None = None
        self.hilo = Thread(target=self._ejecutar, name=f"seguimiento-{nombre}", daemon=False)

    def estado(self) -> dict[str, Any]:
        with self._lock:
            return {
                "estado": self._estado,
                "diagnostico": dict(self._diagnostico) if self._diagnostico else None,
            }

    def _actualizar(self, estado: str, diagnostico: dict[str, str] | None = None) -> None:
        if diagnostico:
            logging.getLogger(__name__).warning("Ciclo %s: %s %s", self.nombre, estado, diagnostico)
        with self._lock:
            self._estado = estado
            self._diagnostico = diagnostico

    def iniciar(self) -> None:
        self.hilo.start()

    def detener(self, timeout: float) -> None:
        self.parada.set()
        self.hilo.join(max(timeout, 0))
        if self.hilo.is_alive():
            raise TimeoutError(f"No termino el ciclo {self.nombre}")
        if self._error_cierre is not None:
            raise self._error_cierre

    def _ejecutar(self) -> None:
        try:
            while not self.parada.is_set():
                try:
                    processed = self.paso()
                    self._actualizar("operativo")
                    if not processed:
                        self.parada.wait(self.pausa)
                except FalloPaso as error:
                    pausado = error.accion == AccionError.PAUSAR
                    self._actualizar("pausado" if pausado else "recuperando", error.diagnostico)
                    if pausado:
                        self.parada.wait()
                    else:
                        self.parada.wait(self.pausa)
                except Exception as error:
                    self._actualizar("pausado", {"motivo": type(error).__name__})
                    self.parada.wait()
        finally:
            try:
                self.cerrar()
            except Exception as error:
                self._error_cierre = error
                self._actualizar("detenido", {"motivo": type(error).__name__})
            else:
                with self._lock:
                    self._estado = "detenido"
