"""
Módulo que contém funções relacionadas às fórmulas de Erlang.
"""

import math
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

def erlang_a(servers: float, intensity: float, patience: float, aht: float) -> dict:
    """Calcula métricas de fila com abandono usando o modelo Erlang A (M/M/N+M).

    Estende o Erlang C modelando a paciência do cliente: chamadas que esperam
    além do limite de paciência abandonam a fila.

    Args:
        servers (float): Número de agentes.
        intensity (float): Taxa de tráfego (erlangs).
        patience (float): Paciência média do cliente (em segundos). Deve ser > 0.
        aht (float): Duração média da chamada (em segundos). Deve ser > 0.

    Returns:
        dict: Dicionário com métricas:
            - 'pw': Probabilidade de espera (ajustada por abandono).
            - 'asa': ASA ajustado por abandono (em fração de intervalo).
            - 'abandon_rate': Fração de chamadas que abandonam.
            - 'sla': Função para calcular SLA dado um tempo alvo.
    """
    if servers <= 0 or intensity <= 0 or patience <= 0 or aht <= 0:
        return {'pw': 0.0, 'asa': 0.0, 'abandon_rate': 0.0, 'sla': lambda t: 1.0}

    theta: float = 1.0 / patience
    rho: float = intensity / servers

    c: float = erlang_c(servers, intensity)

    if rho >= 1.0:
        alpha: float = theta * aht
        pw: float = min_max(c / (c + (1 - c) * (1 + alpha)), 0.0, 1.0)
    else:
        pw = c

    avg_wait_if_queued: float = 1.0 / (servers * (1.0 / aht) * (1 - min(rho, 0.99)) + theta)
    asa_val: float = pw * avg_wait_if_queued

    if theta * avg_wait_if_queued > 50:
        abandon_given_wait: float = 1.0
    else:
        abandon_given_wait = 1.0 - math.exp(-theta * avg_wait_if_queued)
    abandon_rate: float = pw * abandon_given_wait

    def sla_func(target_time: float) -> float:
        if target_time <= 0:
            return 1.0 - pw
        exponent: float = -theta * target_time
        if exponent < -50:
            patience_factor = 0.0
        else:
            patience_factor = math.exp(exponent)
        if rho >= 1.0:
            served_before_t: float = 1.0 - pw * patience_factor
        else:
            erlang_decay: float = (intensity - servers) / aht * target_time
            if erlang_decay < -50:
                erlang_factor = 0.0
            else:
                erlang_factor = math.exp(erlang_decay)
            combined: float = min(erlang_factor, patience_factor)
            served_before_t = 1.0 - pw * combined
        return min_max(served_before_t, 0.0, 1.0)

    return {
        'pw': pw,
        'asa': asa_val,
        'abandon_rate': abandon_rate,
        'sla': sla_func
    }
