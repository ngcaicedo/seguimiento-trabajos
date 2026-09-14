from dataclasses import dataclass
from datetime import datetime

from seguimiento_trabajos.seedwork.dominio.validaciones import normalizar_instante


@dataclass(frozen=True)
class MetadatosProyeccion:
    primera_recepcion_en: datetime
    proyectada_en: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "primera_recepcion_en", normalizar_instante(self.primera_recepcion_en)
        )
        object.__setattr__(self, "proyectada_en", normalizar_instante(self.proyectada_en))
