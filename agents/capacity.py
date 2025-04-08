"""
Módulo para cálculos relacionados a agentes e métricas de atendimento.
"""

import math
from mod_turbotab.calculations.erlang import erlang_c
from mod_turbotab.utils import secs, int_ceiling, min_max
from mod_turbotab.calculations.traffic import traffic
from mod_turbotab.exceptions import CalculationError, InputValidationError
from mod_turbotab.config import INTERVAL, MAX_ACCURACY

def agents_required(sla: float, service_time: int, calls_per_hour: float, aht: int) -> int:
    """Determina o número de agentes necessários para atingir o SLA desejado.

    Args:
        sla (float): Percentual de atendimento esperado (ex: 0.95 para 95%).
        service_time (int): Tempo alvo de atendimento em segundos.
        calls_per_hour (float): Número de chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Número de agentes requeridos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if sla < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para agents_required.")
    try:
        sla = min(sla, 1.0)
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        erlangs: int = int((birth_rate * aht) / INTERVAL + 0.5)
        no_agents: int = 1 if erlangs < 1 else int(erlangs)
        utilisation: float = traffic_rate / no_agents
        while utilisation >= 1:
            no_agents += 1
            utilisation = traffic_rate / no_agents
        max_iterate: int = no_agents * 100
        for _ in range(max_iterate):
            utilisation = traffic_rate / no_agents
            if utilisation < 1:
                c: float = erlang_c(no_agents, traffic_rate)
                sl_queued: float = 1 - c * math.exp((traffic_rate - no_agents) * service_time / aht)
                if sl_queued < 0:
                    sl_queued = 0.0
                if sl_queued >= sla or sl_queued > (1 - MAX_ACCURACY):
                    break
            no_agents += 1
        return no_agents
    except Exception as e:
        raise CalculationError(f"Erro em agents_required: {str(e)}") from e

def asa(agents: float, calls_per_hour: float, aht: int) -> int:
    """Calcula o Average Speed of Answer (ASA) para um dado número de agentes.

    Args:
        agents (float): Número de agentes.
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: ASA em segundos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if agents <= 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para asa.")
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        c: float = erlang_c(agents, traffic_rate)
        answer_time: float = c / (agents * death_rate * (1 - utilisation))
        return secs(answer_time)
    except Exception as e:
        raise CalculationError(f"Erro em asa: {str(e)}") from e

def agents_asa(asa_target: float, calls_per_hour: float, aht: int) -> int:
    """Determina o número de agentes necessários para atingir o ASA alvo.

    Args:
        asa_target (float): ASA alvo (em segundos).
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Número de agentes requeridos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if asa_target < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para agents_asa.")
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        erlangs: int = int((birth_rate * aht) / INTERVAL + 0.5)
        no_agents: int = 1 if erlangs < 1 else int(erlangs)
        utilisation: float = traffic_rate / no_agents
        while utilisation >= 1:
            no_agents += 1
            utilisation = traffic_rate / no_agents
        max_iterate: int = no_agents * 100
        for _ in range(max_iterate):
            c: float = erlang_c(no_agents, traffic_rate)
            answer_time: float = c / (no_agents * death_rate * (1 - utilisation))
            if (answer_time * INTERVAL) <= asa_target:
                break
            no_agents += 1
        return no_agents
    except Exception as e:
        raise CalculationError(f"Erro em agents_asa: {str(e)}") from e

def nb_agents(calls_ph: float, avg_sa: float, avg_ht: int) -> int:
    """Calcula o número de agentes necessários com base no ASA médio.

    Args:
        calls_ph (float): Chamadas por hora.
        avg_sa (float): ASA médio (em segundos).
        avg_ht (int): Duração média da chamada (em segundos).

    Returns:
        int: Número de agentes requeridos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if calls_ph < 0 or avg_sa < 0 or avg_ht <= 0:
        raise InputValidationError("Parâmetros inválidos para nb_agents.")
    try:
        max_iterate: int = 65535
        for count in range(1, max_iterate + 1):
            if asa(float(count), calls_ph, avg_ht) <= avg_sa:
                return count
        raise CalculationError("Não foi possível determinar o número de agentes com nb_agents.")
    except Exception as e:
        raise CalculationError(f"Erro em nb_agents: {str(e)}") from e

def call_capacity(no_agents: float, sla: float, service_time: int, aht: int) -> float:
    """Calcula o número máximo de chamadas que podem ser atendidas pelos agentes mantendo o SLA.

    Args:
        no_agents (float): Número de agentes disponíveis.
        sla (float): SLA alvo (ex: 0.85).
        service_time (int): Tempo alvo de atendimento (em segundos).
        aht (int): Duração média da chamada (em segundos).

    Returns:
        float: Número máximo de chamadas atendidas.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if no_agents < 0 or sla < 0 or service_time < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para call_capacity.")
    try:
        x_no_agent: int = int(no_agents)
        calls: int = int_ceiling(INTERVAL / aht) * x_no_agent
        x_agent: int = agents_required(sla, service_time, calls, aht)
        while x_agent > x_no_agent and calls > 0:
            calls -= 1
            x_agent = agents_required(sla, service_time, calls, aht)
        return float(calls)
    except Exception as e:
        raise CalculationError(f"Erro em call_capacity: {str(e)}") from e

def fractional_agents(sla: float, service_time: int, calls_per_hour: float, aht: int) -> float:
    """Calcula o número fracionário de agentes necessários para atingir o SLA desejado.

    Args:
        sla (float): SLA alvo (ex: 0.95).
        service_time (int): Tempo alvo de atendimento (em segundos).
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        float: Número fracionário de agentes.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if sla < 0 or calls_per_hour < 0 or aht <= 0 or service_time < 0:
        raise InputValidationError("Parâmetros inválidos para fractional_agents.")
    try:
        sla = min(sla, 1.0)
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        erlangs: int = int((birth_rate * aht) / INTERVAL + 0.5)
        no_agents: int = 1 if erlangs < 1 else int(erlangs)
        utilisation: float = traffic_rate / no_agents
        while utilisation >= 1:
            no_agents += 1
            utilisation = traffic_rate / no_agents
        sl_queued: float = 0.0
        max_iterate: int = no_agents * 100
        last_slq: float = 0.0
        for _ in range(max_iterate):
            last_slq = sl_queued
            utilisation = traffic_rate / no_agents
            if utilisation < 1:
                c: float = erlang_c(no_agents, traffic_rate)
                sl_queued = 1 - c * math.exp((traffic_rate - no_agents) * service_time / aht)
                if sl_queued < 0:
                    sl_queued = 0.0
                if sl_queued > 1:
                    sl_queued = 1.0
                if sl_queued >= sla or sl_queued > (1 - MAX_ACCURACY):
                    break
            no_agents += 1
        no_agents_sng: float = float(no_agents)
        if sl_queued > sla:
            one_agent_effect: float = sl_queued - last_slq
            fract: float = sla - last_slq
            no_agents_sng = (fract / one_agent_effect) + (no_agents - 1)
        return no_agents_sng
    except Exception as e:
        raise CalculationError(f"Erro em fractional_agents: {str(e)}") from e

def fractional_call_capacity(no_agents: float, sla: float, service_time: int, aht: int) -> float:
    """Calcula o número máximo de chamadas que podem ser atendidas por um número fracionário de agentes mantendo o SLA.

    Args:
        no_agents (float): Número fracionário de agentes disponíveis.
        sla (float): SLA alvo (ex: 0.85).
        service_time (int): Tempo alvo de atendimento (em segundos).
        aht (int): Duração média da chamada (em segundos).

    Returns:
        float: Número máximo de chamadas atendidas.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if no_agents < 0 or sla < 0 or service_time < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para fractional_call_capacity.")
    try:
        x_no_agent: float = no_agents
        calls: int = int_ceiling((INTERVAL / aht) * x_no_agent)
        x_agent: float = fractional_agents(sla, service_time, calls, aht)
        while x_agent > x_no_agent and calls > 0:
            calls -= 1
            x_agent = fractional_agents(sla, service_time, calls, aht)
        return float(calls)
    except Exception as e:
        raise CalculationError(f"Erro em fractional_call_capacity: {str(e)}") from e
