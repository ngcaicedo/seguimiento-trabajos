from threading import Event

from seguimiento_trabajos.seedwork.infraestructura.ciclos import AccionError, Ciclo, FalloPaso


def test_pausa_no_reintenta_y_parada_cierra() -> None:
    ejecutado = Event()
    cerrado = Event()
    pasos: list[int] = []

    def paso() -> bool:
        pasos.append(1)
        ejecutado.set()
        raise FalloPaso(AccionError.PAUSAR, {"motivo": "invalido"})

    ciclo = Ciclo("prueba", paso, cerrado.set, pausa=0.01)
    ciclo.iniciar()
    assert ejecutado.wait(1)
    ciclo.detener(1)
    assert cerrado.is_set()
    assert pasos == [1]
    assert not ciclo.hilo.is_alive()


def test_recuperacion_borra_diagnostico_y_parada_interrumpe_espera() -> None:
    recuperado = Event()
    pasos: list[int] = []

    def paso() -> bool:
        pasos.append(1)
        if len(pasos) == 1:
            raise FalloPaso(AccionError.REINTENTAR, {"motivo": "temporal"})
        recuperado.set()
        return False

    ciclo = Ciclo("prueba", paso, lambda: None, pausa=0.01)
    ciclo.iniciar()
    assert recuperado.wait(1)
    ciclo.detener(1)
    assert ciclo.estado()["diagnostico"] is None


def test_error_de_cierre_se_propaga_al_supervisor() -> None:
    import pytest

    ejecutado = Event()

    def paso() -> bool:
        ejecutado.set()
        return False

    def cerrar() -> None:
        raise RuntimeError("cierre fallido")

    ciclo = Ciclo("prueba", paso, cerrar)
    ciclo.iniciar()
    assert ejecutado.wait(1)
    with pytest.raises(RuntimeError, match="cierre fallido"):
        ciclo.detener(1)
