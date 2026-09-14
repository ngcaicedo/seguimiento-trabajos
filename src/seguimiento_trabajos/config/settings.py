import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = "seguimiento-trabajos"
    database_url: str | None = None
    processing_enabled: bool = False
    pulsar_url: str = "pulsar://127.0.0.1:6650"
    topico_creacion: str = "persistent://public/default/trabajo-creado-v1"
    topico_registrada: str = "persistent://public/default/cotizacion-registrada-v1"
    topico_rechazada: str = "persistent://public/default/cotizacion-rechazada-v1"
    recepcion_ms: int = 500
    reentrega_ms: int = 1000
    pausa_reintento: float = 0.5

    def __post_init__(self) -> None:
        if self.processing_enabled and not self.database_url:
            raise ValueError("El procesamiento requiere SEGUIMIENTO_DATABASE_URL")
        if not self.pulsar_url.startswith(("pulsar://", "pulsar+ssl://")):
            raise ValueError("URL Pulsar invalida")
        if any(
            not topico.startswith("persistent://")
            for topico in (
                self.topico_creacion,
                self.topico_registrada,
                self.topico_rechazada,
            )
        ):
            raise ValueError("Los topicos deben ser persistentes")
        if len({self.topico_creacion, self.topico_registrada, self.topico_rechazada}) != 3:
            raise ValueError("Cada contrato requiere un topico distinto")
        if (
            not 1 <= self.recepcion_ms <= 1000
            or self.reentrega_ms < 1000
            or not 0 < self.pausa_reintento <= 30
        ):
            raise ValueError("Limites de procesamiento invalidos")

    @classmethod
    def from_environment(cls) -> "Settings":
        habilitado = os.getenv("SEGUIMIENTO_PROCESSING_ENABLED", "false").strip().lower()
        if habilitado not in ("true", "false"):
            raise ValueError("SEGUIMIENTO_PROCESSING_ENABLED requiere true o false")
        return cls(
            service_name=os.environ.get("SEGUIMIENTO_SERVICE_NAME", "seguimiento-trabajos"),
            database_url=os.environ.get("SEGUIMIENTO_DATABASE_URL", "").strip() or None,
            processing_enabled=habilitado == "true",
            pulsar_url=os.getenv("SEGUIMIENTO_PULSAR_URL", cls.pulsar_url),
            topico_creacion=os.getenv("SEGUIMIENTO_TOPICO_CREACION", cls.topico_creacion),
            topico_registrada=os.getenv("SEGUIMIENTO_TOPICO_REGISTRADA", cls.topico_registrada),
            topico_rechazada=os.getenv("SEGUIMIENTO_TOPICO_RECHAZADA", cls.topico_rechazada),
            recepcion_ms=int(os.getenv("SEGUIMIENTO_RECEPCION_MS", "500")),
            reentrega_ms=int(os.getenv("SEGUIMIENTO_REENTREGA_MS", "1000")),
            pausa_reintento=float(os.getenv("SEGUIMIENTO_PAUSA_REINTENTO", "0.5")),
        )
