"""
Módulo para cálculos específicos de trunks.

Contém funções como number_trunks e trunks_required, com validação de entrada,
tratamento de exceções personalizado e tipagem completa.
"""

from mod_turbotab.config import INTERVAL
from mod_turbotab.utils import int_ceiling, secs
from mod_turbotab.calculations.erlang import erlang_b, erlang_c
from mod_turbotab.exceptions import CalculationError, InputValidationError

def number_trunks(servers: float, intensity: float) -> int:
    """Determina o número máximo de trunks requeridos para atender chamadas enfileiradas e atendidas.

    Args:
        servers (float): Número de agentes/servidores.
        intensity (float): Taxa de tráfego (em erlangs).

    Returns:
        int: Número de trunks necessários.

    Raises:
        InputValidationError: Se os parâmetros forem negativos.
        CalculationError: Se não for possível determinar um valor adequado dentro dos limites.
    """
    if servers < 0 or intensity < 0:
        raise InputValidationError("Os valores de 'servers' e 'intensity' devem ser não negativos.")
    
    max_iterate: int = 65535
    try:
        start: int = int_ceiling(servers)
        for count in range(start, max_iterate + 1):
            b: float = erlang_b(float(count), intensity)
            if b < 0.001:
                return count
        raise CalculationError("Não foi possível determinar um número adequado de trunks dentro do limite máximo.")
    except Exception as e:
        raise CalculationError(f"Erro ao calcular o número de trunks: {str(e)}") from e

def trunks_required(agents: float, calls_per_hour: float, aht: int) -> int:
    """Calcula o número de trunks necessários para atender o volume de chamadas.

    Args:
        agents (float): Número de agentes.
        calls_per_hour (float): Chamadas por hora.
        aht (int): Duração média da chamada (em segundos).

    Returns:
        int: Número de trunks necessários.

    Raises:
        InputValidationError: Se os parâmetros forem inválidos (negativos ou AHT não positivo).
        CalculationError: Se ocorrer erro durante o cálculo.
    """
    if agents < 0 or calls_per_hour < 0 or aht <= 0:
        raise InputValidationError("Valores inválidos para 'agents', 'calls_per_hour' ou 'aht'.")
    
    try:
        birth_rate: float = calls_per_hour
        death_rate: float = INTERVAL / aht
        traffic_rate: float = birth_rate / death_rate
        utilisation: float = traffic_rate / agents
        if utilisation >= 1:
            utilisation = 0.99
        c: float = erlang_c(agents, traffic_rate)
        answer_time: float = c / (agents * death_rate * (1 - utilisation))
        r: float = birth_rate / (INTERVAL / (aht + secs(answer_time)))
        no_trunks: int = number_trunks(agents, r)
        if no_trunks < 1 and traffic_rate > 0:
            no_trunks = 1
        return no_trunks
    except Exception as e:
        raise CalculationError(f"Erro no cálculo dos trunks: {str(e)}") from e
