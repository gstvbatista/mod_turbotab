"""
Módulo para cálculos relacionados à intensidade de tráfego.
"""

import math
from mod_turbotab.calculations.erlang import erlang_b
from mod_turbotab.utils import int_ceiling

MAX_ACCURACY: float = 0.00001
MAX_LOOPS: int = 100

def looping_traffic(trunks: float, blocking: float, increment: float, max_intensity: float, min_intensity: float) -> float:
    """Aproxima iterativamente a intensidade de tráfego para um dado número de trunks e bloqueio.

    Args:
        trunks (float): Número de trunks.
        blocking (float): Fator de bloqueio desejado.
        increment (float): Incremento inicial.
        max_intensity (float): Valor máximo de intensidade considerado.
        min_intensity (float): Valor mínimo de intensidade considerado.

    Returns:
        float: Intensidade de tráfego aproximada.
    """
    min_i: float = min_intensity
    intensity: float = min_i
    loop_no: int = 0
    while increment >= MAX_ACCURACY and loop_no < MAX_LOOPS:
        b: float = erlang_b(trunks, intensity)
        if b > blocking:
            max_intensity = intensity
            increment /= 10
            intensity = min_i
        min_i = intensity
        intensity += increment
        loop_no += 1
    return min_i

def traffic(servers: float, blocking: float) -> float:
    """Calcula a intensidade de tráfego (em erlangs) para um dado número de servidores e bloqueio.

    Args:
        servers (float): Número de trunks disponíveis.
        blocking (float): Fator de bloqueio alcançado.

    Returns:
        float: Intensidade de tráfego.
    """
    trunks_val: float = float(int(servers))
    if servers < 1 or blocking < 0:
        return 0.0
    max_i: float = trunks_val
    b: float = erlang_b(servers, max_i)
    while b < blocking:
        max_i *= 2
        b = erlang_b(servers, max_i)
    incr: float = 1.0
    while incr <= max_i / 100:
        incr *= 10
    return looping_traffic(trunks_val, blocking, incr, max_i, 0.0)
