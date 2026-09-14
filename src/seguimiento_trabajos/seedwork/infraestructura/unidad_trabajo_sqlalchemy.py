from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType
from typing import ClassVar, Self

from psycopg.errors import UniqueViolation
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from seguimiento_trabajos.seedwork.aplicacion.excepciones import ColisionPersistencia


class UnidadTrabajoSQL(ABC):
    restricciones_reintentables: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, crear_sesion: Callable[[], Session]) -> None:
        self._crear_sesion = crear_sesion
        self._sesion: Session | None = None
        self._activa = False

    @property
    def sesion(self) -> Session:
        if self._sesion is None or not self._activa:
            raise RuntimeError("Unidad de trabajo inactiva")
        return self._sesion

    def __enter__(self) -> Self:
        if self._sesion is not None:
            raise RuntimeError("Unidad de trabajo ya abierta")
        self._sesion = self._crear_sesion()
        self._activa = True
        try:
            self.sesion.autoflush = False
            self.sesion.begin()
            self._crear_repositorios()
        except BaseException:
            self._sesion.close()
            self._sesion = None
            self._activa = False
            raise
        return self

    def __exit__(
        self,
        tipo_error: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        try:
            self.revertir()
        finally:
            if self._sesion is not None:
                self._sesion.close()
            self._sesion = None
        if isinstance(error, IntegrityError) and isinstance(error.orig, UniqueViolation):
            if error.orig.diag.constraint_name in self.restricciones_reintentables:
                raise ColisionPersistencia("Colision concurrente de persistencia") from error

    def confirmar(self) -> None:
        self.sesion.flush()
        self.sesion.commit()
        self._activa = False

    def revertir(self) -> None:
        try:
            if self._sesion is not None:
                self._sesion.rollback()
        finally:
            self._activa = False

    @abstractmethod
    def _crear_repositorios(self) -> None: ...
