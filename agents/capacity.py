"""
Módulo para cálculos relacionados a agentes e métricas de atendimento.
"""

import math
from mod_turbotab.calculations.erlang import erlang_c, erlang_a
from mod_turbotab.utils import secs, int_ceiling, min_max
from mod_turbotab.calculations.traffic import traffic
from mod_turbotab.exceptions import CalculationError, InputValidationError
from mod_turbotab.config import INTERVAL, MAX_ACCURACY

def agents_required(sla: float, service_time: int, calls_per_interval: float, aht: int, patience: float = None) -> int:
    """Determina o número de agentes necessários para atingir o SLA desejado.

    Args:
        sla (float): Percentual de atendimento esperado (ex: 0.95 para 95%).
        service_time (int): Tempo alvo de atendimento em segundos.
        calls_per_interval (float): Chamadas por intervalo (conforme config.INTERVAL).
        aht (int): Duração média da chamada (em segundos).
        patience (float, optional): Paciência média do cliente em segundos (Erlang A).
            Se None, usa Erlang C puro.

    Returns:
        int: Número de agentes requeridos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if sla < 0 or calls_per_interval < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para agents_required.")
    try:
        sla = min(sla, 1.0)
        birth_rate: float = calls_per_interval
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate

        def _sla_at(n: int) -> float:
            if traffic_rate / n >= 1:
                return 0.0
            if patience is not None:
                ea: dict = erlang_a(n, traffic_rate, patience, aht)
                return ea['sla'](service_time)
            c: float = erlang_c(n, traffic_rate)
            val: float = 1 - c * math.exp((traffic_rate - n) * service_time / aht)
            return max(val, 0.0)

        lo: int = max(1, int(math.ceil(traffic_rate)) + 1)
        hi: int = lo
        while _sla_at(hi) < sla:
            hi *= 2
        while lo < hi:
            mid: int = (lo + hi) // 2
            if _sla_at(mid) >= sla:
                hi = mid
            else:
                lo = mid + 1
        return lo
    except Exception as e:
        raise CalculationError(f"Erro em agents_required: {str(e)}") from e

def asa(agents: float, calls_per_interval: float, aht: int, patience: float = None) -> int:
    """Calcula o Average Speed of Answer (ASA) para um dado número de agentes.

    Args:
        agents (float): Número de agentes.
        calls_per_interval (float): Chamadas por intervalo (conforme config.INTERVAL).
        aht (int): Duração média da chamada (em segundos).
        patience (float, optional): Paciência média do cliente em segundos (Erlang A).
            Se None, usa Erlang C puro.

    Returns:
        int: ASA em segundos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if agents <= 0 or calls_per_interval < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para asa.")
    try:
        birth_rate: float = calls_per_interval
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        if patience is not None:
            ea: dict = erlang_a(agents, traffic_rate, patience, aht)
            return int(ea['asa'] + 0.5)
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        c: float = erlang_c(agents, traffic_rate)
        answer_time: float = c / (agents * death_rate * (1 - utilisation))
        return secs(answer_time)
    except Exception as e:
        raise CalculationError(f"Erro em asa: {str(e)}") from e

def agents_asa(asa_target: float, calls_per_interval: float, aht: int) -> int:
    """Determina o número de agentes necessários para atingir o ASA alvo.

    Args:
        asa_target (float): ASA alvo (em segundos).
        calls_per_interval (float): Chamadas por intervalo (conforme config.INTERVAL).
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Número de agentes requeridos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if asa_target < 0 or calls_per_interval < 0 or aht <= 0:
        raise InputValidationError("Parâmetros inválidos para agents_asa.")
    try:
        birth_rate: float = calls_per_interval
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate

        def _asa_at(n: int) -> float:
            utilisation: float = traffic_rate / n
            if utilisation >= 1:
                return float('inf')
            c: float = erlang_c(n, traffic_rate)
            answer_time: float = c / (n * death_rate * (1 - utilisation))
            return answer_time * INTERVAL

        lo: int = max(1, int(math.ceil(traffic_rate)) + 1)
        hi: int = lo
        while _asa_at(hi) > asa_target:
            hi *= 2
        while lo < hi:
            mid: int = (lo + hi) // 2
            if _asa_at(mid) <= asa_target:
                hi = mid
            else:
                lo = mid + 1
        return lo
    except Exception as e:
        raise CalculationError(f"Erro em agents_asa: {str(e)}") from e

def nb_agents(calls_per_interval: float, avg_sa: float, avg_ht: int) -> int:
    """Calcula o número de agentes necessários com base no ASA médio.

    Args:
        calls_per_interval (float): Chamadas por intervalo (conforme config.INTERVAL).
        avg_sa (float): ASA médio (em segundos).
        avg_ht (int): Duração média da chamada (em segundos).

    Returns:
        int: Número de agentes requeridos.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if calls_per_interval < 0 or avg_sa < 0 or avg_ht <= 0:
        raise InputValidationError("Parâmetros inválidos para nb_agents.")
    try:
        birth_rate: float = calls_per_interval
        death_rate: float = INTERVAL / avg_ht
        traffic_rate: float = birth_rate / death_rate
        lo: int = max(1, int(math.ceil(traffic_rate)) + 1)
        hi: int = lo
        while asa(float(hi), calls_per_interval, avg_ht) > avg_sa:
            hi *= 2
            if hi > 65535:
                raise CalculationError("Não foi possível determinar o número de agentes com nb_agents.")
        while lo < hi:
            mid: int = (lo + hi) // 2
            if asa(float(mid), calls_per_interval, avg_ht) <= avg_sa:
                hi = mid
            else:
                lo = mid + 1
        return lo
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

def fractional_agents(sla: float, service_time: int, calls_per_interval: float, aht: int, patience: float = None) -> float:
    """Calcula o número fracionário de agentes necessários para atingir o SLA desejado.

    Args:
        sla (float): SLA alvo (ex: 0.95).
        service_time (int): Tempo alvo de atendimento (em segundos).
        calls_per_interval (float): Chamadas por intervalo (conforme config.INTERVAL).
        aht (int): Duração média da chamada (em segundos).
        patience (float, optional): Paciência média do cliente em segundos (Erlang A).
            Se None, usa Erlang C puro.

    Returns:
        float: Número fracionário de agentes.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos.
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if sla < 0 or calls_per_interval < 0 or aht <= 0 or service_time < 0:
        raise InputValidationError("Parâmetros inválidos para fractional_agents.")
    try:
        sla = min(sla, 1.0)
        birth_rate: float = calls_per_interval
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate

        def _sla_at(n: int) -> float:
            if traffic_rate / n >= 1:
                return 0.0
            if patience is not None:
                ea: dict = erlang_a(n, traffic_rate, patience, aht)
                return min_max(ea['sla'](service_time), 0.0, 1.0)
            c: float = erlang_c(n, traffic_rate)
            val: float = 1 - c * math.exp((traffic_rate - n) * service_time / aht)
            return min_max(val, 0.0, 1.0)

        lo: int = max(1, int(math.ceil(traffic_rate)) + 1)
        hi: int = lo
        while _sla_at(hi) < sla:
            hi *= 2
        while lo < hi:
            mid: int = (lo + hi) // 2
            if _sla_at(mid) >= sla:
                hi = mid
            else:
                lo = mid + 1
        no_agents: int = lo
        sl_queued: float = _sla_at(no_agents)
        last_slq: float = _sla_at(no_agents - 1) if no_agents > 1 else 0.0
        no_agents_sng: float = float(no_agents)
        if sl_queued > sla and (sl_queued - last_slq) > 0:
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
