import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from time import monotonic
from typing import Any

from sqlalchemy import text

from seguimiento_trabajos.config.bootstrap import componer_consumidores
from seguimiento_trabajos.config.database import Database
from seguimiento_trabajos.config.settings import Settings
from seguimiento_trabajos.seedwork.infraestructura.ciclos import Ciclo

PRESUPUESTO_CIERRE = 9.0


@dataclass
class Procesamiento:
    base: Database
    ciclos: list[Ciclo] = field(default_factory=list)
    cerrando: bool = False

    def salud(self) -> dict[str, Any]:
        fuentes = {ciclo.nombre: ciclo.estado() for ciclo in self.ciclos}
        database_ok = False
        try:
            with self.base.engine.connect() as conexion:
                conexion.execute(text("SELECT 1"))
            database_ok = True
        except Exception:
            pass
        listo = (
            not self.cerrando
            and database_ok
            and len(fuentes) == 3
            and all(estado["estado"] == "operativo" for estado in fuentes.values())
        )
        return {
            "status": "ok" if listo else "unavailable",
            "database": database_ok,
            "fuentes": fuentes,
        }

    def cerrar(self) -> None:
        self.cerrando = True
        limite = monotonic() + PRESUPUESTO_CIERRE
        for ciclo in self.ciclos:
            ciclo.parada.set()
        errores: list[Exception] = []
        for ciclo in self.ciclos:
            try:
                ciclo.detener(limite - monotonic())
            except Exception as error:
                errores.append(error)
        if errores:
            raise ExceptionGroup("Fallo de cierre de consumidores", errores)


@asynccontextmanager
async def procesar_eventos(
    base: Database, settings: Settings
) -> AsyncIterator[Procesamiento | None]:
    if not settings.processing_enabled:
        yield None
        return
    procesamiento = Procesamiento(base)
    try:
        consumidores = await asyncio.to_thread(componer_consumidores, base, settings)
        for consumidor in consumidores:
            ciclo = Ciclo(
                consumidor.suscripcion,
                consumidor.procesar_siguiente,
                consumidor.cerrar,
                settings.pausa_reintento,
            )
            ciclo.iniciar()
            procesamiento.ciclos.append(ciclo)
        yield procesamiento
    finally:
        procesamiento.cerrando = True
        await asyncio.to_thread(procesamiento.cerrar)
