"""
Módulo que contém funções relacionadas às fórmulas de Erlang.
"""

from mod_turbotab.utils import min_max, int_ceiling

def erlang_b(servers: float, intensity: float) -> float:
    """Calcula a probabilidade de bloqueio com a fórmula de Erlang B.

    Args:
        servers (float): Número de linhas telefônicas.
        intensity (float): Taxa de tráfego.

    Returns:
        float: Probabilidade de bloqueio (entre 0 e 1).
    """
    if servers < 0 or intensity < 0:
        return 0.0
    max_iterate: int = int(servers)
    last: float = 1.0
    for count in range(1, max_iterate + 1):
        b: float = (intensity * last) / (count + intensity * last)
        last = b
    return min_max(b, 0.0, 1.0)

def erlang_b_ext(servers: float, intensity: float, retry: float) -> float:
    """Calcula a probabilidade de bloqueio com a fórmula estendida de Erlang B.

    Args:
        servers (float): Número de linhas telefônicas.
        intensity (float): Taxa de tráfego.
        retry (float): Percentual de chamadas que tentam novamente (ex.: 0.1 para 10%).

    Returns:
        float: Probabilidade de bloqueio (entre 0 e 1).
    """
    if servers < 0 or intensity < 0:
        return 0.0
    max_iterate: int = int(servers)
    retries: float = min_max(retry, 0.0, 1.0)
    last: float = 1.0
    for count in range(1, max_iterate + 1):
        b: float = (intensity * last) / (count + intensity * last)
        attempts: float = 1.0 / (1 - (b * retries))
        b = (intensity * last * attempts) / (count + intensity * last * attempts)
        last = b
    return min_max(b, 0.0, 1.0)

def engset_b(servers: float, events: float, intensity: float) -> float:
    """Calcula a probabilidade de bloqueio usando a fórmula de Engset B.

    Args:
        servers (float): Número de linhas telefônicas.
        events (float): Número total de chamadas.
        intensity (float): Intensidade média por chamada.

    Returns:
        float: Probabilidade de bloqueio (entre 0 e 1).
    """
    if servers < 0 or intensity < 0:
        return 0.0
    max_iterate: int = int(servers)
    val: float = intensity
    ev: float = events
    last: float = 1.0
    for count in range(1, max_iterate + 1):
        b: float = (last * (count / ((ev - count) * val))) + 1
        last = b
    return 0.0 if b == 0 else min_max((1 / b), 0.0, 1.0)

def erlang_c(servers: float, intensity: float) -> float:
    """Calcula a probabilidade de enfileiramento com a fórmula de Erlang C.

    Args:
        servers (float): Número de agentes.
        intensity (float): Taxa de tráfego.

    Returns:
        float: Probabilidade de enfileiramento (entre 0 e 1).
    """
    if servers < 0 or intensity < 0:
        return 0.0
    b: float = erlang_b(servers, intensity)
    c: float = b / (((intensity / servers) * b) + (1 - (intensity / servers)))
    return min_max(c, 0.0, 1.0)
