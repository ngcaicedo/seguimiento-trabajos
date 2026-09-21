import os
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Settings:
    service_name: str = "seguimiento-trabajos"
    database_url: str | None = None
    processing_enabled: bool = False
    pulsar_url: str = "pulsar://127.0.0.1:6650"
    topico_creacion: str = "persistent://public/default/trabajo-creado-v1"
    topico_registrada: str = "persistent://public/default/cotizacion-registrada-v1"
    topico_rechazada: str = "persistent://public/default/cotizacion-rechazada-v1"
    topico_apertura: str = "persistent://public/default/abrir-seguimiento-trabajo-v1"
    topico_cancelacion: str = "persistent://public/default/cancelar-seguimiento-trabajo-v1"
    topico_trabajo_cancelado: str = "persistent://public/default/trabajo-cancelado-v1"
    topico_abierto: str = "persistent://public/default/seguimiento-trabajo-abierto-v1"
    topico_apertura_fallida: str = "persistent://public/default/apertura-seguimiento-fallida-v1"
    topico_cancelado: str = "persistent://public/default/seguimiento-trabajo-cancelado-v1"
    fail_opening_work_id: UUID | None = None
    recepcion_ms: int = 500
    reentrega_ms: int = 1000
    pausa_reintento: float = 0.5

    def __post_init__(self) -> None:
        if self.processing_enabled and not self.database_url:
            raise ValueError("El procesamiento requiere SEGUIMIENTO_DATABASE_URL")
        if not self.pulsar_url.startswith(("pulsar://", "pulsar+ssl://")):
            raise ValueError("URL Pulsar invalida")
        topics = (
            self.topico_creacion,
            self.topico_registrada,
            self.topico_rechazada,
            self.topico_apertura,
            self.topico_cancelacion,
            self.topico_trabajo_cancelado,
            self.topico_abierto,
            self.topico_apertura_fallida,
            self.topico_cancelado,
        )
        if self.fail_opening_work_id is not None and self.fail_opening_work_id.int == 0:
            raise ValueError("ID de fallo controlado invalido")
        if any(not topico.startswith("persistent://") for topico in topics):
            raise ValueError("Los topicos deben ser persistentes")
        if len(set(topics)) != len(topics):
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
            topico_apertura=os.getenv("SEGUIMIENTO_TOPICO_APERTURA", cls.topico_apertura),
            topico_cancelacion=os.getenv("SEGUIMIENTO_TOPICO_CANCELACION", cls.topico_cancelacion),
            topico_trabajo_cancelado=os.getenv(
                "SEGUIMIENTO_TOPICO_TRABAJO_CANCELADO", cls.topico_trabajo_cancelado
            ),
            topico_abierto=os.getenv("SEGUIMIENTO_TOPICO_ABIERTO", cls.topico_abierto),
            topico_apertura_fallida=os.getenv(
                "SEGUIMIENTO_TOPICO_APERTURA_FALLIDA", cls.topico_apertura_fallida
            ),
            topico_cancelado=os.getenv("SEGUIMIENTO_TOPICO_CANCELADO", cls.topico_cancelado),
            fail_opening_work_id=(
                UUID(os.environ["SEGUIMIENTO_FAIL_OPENING_WORK_ID"])
                if os.getenv("SEGUIMIENTO_FAIL_OPENING_WORK_ID", "").strip()
                else None
            ),
            recepcion_ms=int(os.getenv("SEGUIMIENTO_RECEPCION_MS", "500")),
            reentrega_ms=int(os.getenv("SEGUIMIENTO_REENTREGA_MS", "1000")),
            pausa_reintento=float(os.getenv("SEGUIMIENTO_PAUSA_REINTENTO", "0.5")),
        )
