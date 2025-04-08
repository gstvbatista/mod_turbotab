"""
Módulo para cálculos relacionados a filas e métricas de atendimento.
"""

import math
from mod_turbotab.calculations.erlang import erlang_c
from mod_turbotab.utils import secs, min_max
from mod_turbotab.exceptions import CalculationError, InputValidationError
from mod_turbotab.config import INTERVAL

def queued(agents: float, calls_per_hour: float, aht: int) -> float:
    """Calcula o percentual de chamadas que ficarão enfileiradas.

    Args:
        agents (float): Número de agentes.
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        float: Percentual de chamadas enfileiradas (entre 0 e 1).

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
    """
    if agents < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para queued.")
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        q: float = erlang_c(agents, traffic_rate)
        return min_max(q, 0.0, 1.0)
    except Exception as e:
        raise CalculationError(f"Erro em queued: {str(e)}") from e

def queue_size(agents: float, calls_per_hour: float, aht: int) -> int:
    """Calcula o tamanho médio da fila (número de chamadas).

    Args:
        agents (float): Número de agentes.
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Tamanho médio da fila (arredondado).

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
    """
    if agents < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para queue_size.")
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        c: float = erlang_c(agents, traffic_rate)
        qsize: float = (utilisation * c) / (1 - utilisation)
        return int(qsize + 0.5)
    except Exception as e:
        raise CalculationError(f"Erro em queue_size: {str(e)}") from e

def queue_time(agents: float, calls_per_hour: float, aht: int) -> int:
    """Calcula o tempo médio de espera na fila (em segundos).

    Args:
        agents (float): Número de agentes.
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Tempo médio de espera na fila.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
    """
    if agents < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para queue_time.")
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        qtime: float = 1 / (agents * death_rate * (1 - utilisation))
        return secs(qtime)
    except Exception as e:
        raise CalculationError(f"Erro em queue_time: {str(e)}") from e

def service_time(agents: float, sla: float, calls_per_hour: float, aht: int) -> int:
    """Calcula o tempo médio de espera para que uma dada porcentagem de chamadas seja atendida.

    Args:
        agents (float): Número de agentes.
        sla (float): SLA alvo (ex: 0.85).
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Tempo de serviço (em segundos).

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if agents < 0 or sla < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para service_time.")
    try:
        adjust: float = 0.0
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        c: float = erlang_c(agents, traffic_rate)
        if c < (1 - sla):
            raise CalculationError("Nenhuma chamada enfileirada; tempo de serviço é 0")
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        qtime: float = 1 / (agents * death_rate * (1 - utilisation)) * INTERVAL
        stime: float = qtime * (1 - ((1 - sla) / c))
        if stime < 0:
            adjust = 1.0
        return int(stime + adjust)
    except Exception as e:
        raise CalculationError(f"Erro em service_time: {str(e)}") from e

def sla_metric(agents: float, service_time_val: float, calls_per_hour: float, aht: int) -> float:
    """Calcula o SLA alcançado para um número dado de agentes.

    Args:
        agents (float): Número de agentes.
        service_time_val (float): Tempo alvo de atendimento (em segundos).
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        float: SLA alcançado (entre 0 e 1).

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if agents < 0 or calls_per_hour < 0 or aht <= 0 or service_time_val < 0:
        raise InputValidationError("Parâmetros inválidos para sla_metric.")
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        c: float = erlang_c(agents, traffic_rate)
        sl_queued: float = 1 - c * math.exp((traffic_rate - agents) * service_time_val / aht)
        return min_max(sl_queued, 0.0, 1.0)
    except Exception as e:
        raise CalculationError(f"Erro em sla_metric: {str(e)}") from e
