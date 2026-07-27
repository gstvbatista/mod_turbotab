"""
Multiplicador de turnos: assentos escalados -> operadores na escala.

A cadeia de shrinkage (#25) para em ``scheduled_agents`` — assentos por
intervalo. Operações contratam **pessoas**, e um assento é coberto por mais
de uma pessoa ao longo do dia operacional: uma operação de 12 horas com
turnos de 6 horas precisa de 2 operadores por assento.

    HC_escala = ceil(HC_escalado * M)

Onde ``M`` é o multiplicador de turnos (operadores por assento ao longo do
dia). Planilhas de referência de tráfego chamam esse fator de "Taxa de
Ocupação" — nome sobrecarregado que **não** é a ocupação Erlang
(``max_occupancy``); aqui ele recebe um nome próprio (issue #26).

O arredondamento é por etapa: os assentos já chegam inteiros de
:func:`scheduled_agents`, e o produto é arredondado para cima — nunca
subdimensiona em relação ao arredondamento único no fim.
"""

import math
from fractions import Fraction

from mod_turbotab.exceptions import InputValidationError


def _validate_finite_product(product: float, scheduled_agents: float, shifts: float) -> None:
    """Rejeita produtos que estouram o intervalo de float.

    Dois valores finitos podem multiplicar para ``inf`` (ex.: ``shifts``
    próximo de ``1e308``); sem esta checagem a cadeia fracionária emitiria
    ``Infinity`` na saída JSON — que não é JSON válido — e a inteira
    devolveria um headcount astronômico sem sentido operacional.
    """
    if not math.isfinite(product):
        raise InputValidationError(
            "scheduled_agents * shifts must be finite. "
            f"Received: scheduled_agents={scheduled_agents}, shifts={shifts}."
        )


def _validate_scheduled_agents(scheduled_agents: float) -> None:
    """Rejeita headcounts escalados negativos ou não-finitos.

    NaN compara falso com qualquer limite, então uma checagem apenas de
    negativo deixaria NaN (e inf) passarem e se propagarem para os
    resultados e para a saída JSON.
    """
    if not math.isfinite(scheduled_agents) or scheduled_agents < 0:
        raise InputValidationError(
            "scheduled_agents must be a finite value >= 0. "
            f"Received: {scheduled_agents}."
        )


def _validate_shifts(shifts: float) -> None:
    """Rejeita multiplicadores de turnos inválidos.

    Cada assento aberto em cada intervalo precisa de um operador presente,
    então o piso físico de operadores é o número de assentos — ``M < 1``
    não tem cenário real e ``M >= 1`` é exigido (decisão da issue #26;
    afrouxar depois é MINOR, apertar depois é breaking). Valores
    não-finitos (NaN/inf) escapam das checagens de intervalo e se
    propagariam para a saída JSON.
    """
    if not math.isfinite(shifts) or shifts < 1.0:
        raise InputValidationError(
            f"Shifts must be a finite value >= 1.0. Received: {shifts}."
        )


def rostered_agents(scheduled_agents: int, shifts: float) -> int:
    """Multiplica assentos escalados pelo fator de turnos, arredondando para cima.

    Args:
        scheduled_agents (int): Assentos por intervalo já inflados por
            shrinkage (ex.: a saída de :func:`scheduled_agents` em
            ``agents/shrinkage.py``).
        shifts (float): Operadores por assento ao longo do dia operacional,
            ``>= 1.0``. Aceita valores fracionários (ex.: ``1.5``).
            ``1.0`` retorna ``scheduled_agents`` sem alteração.

    Returns:
        int: Operadores na escala, arredondado para cima.

    Raises:
        InputValidationError: Se ``shifts`` for menor que ``1.0`` ou
            não-finito, ``scheduled_agents`` for negativo, ou o produto
            estourar o intervalo de float.
    """
    _validate_scheduled_agents(scheduled_agents)
    _validate_shifts(shifts)
    _validate_finite_product(float(scheduled_agents) * shifts, scheduled_agents, shifts)
    if shifts == 1.0:
        return int(scheduled_agents)
    # Aritmética racional exata sobre o valor DECIMAL de ``shifts`` (o
    # shortest-repr do float, que é o que o usuário digitou): elimina
    # qualquer tolerância. 10 * 1.1 é exatamente 11 (e não o float
    # 11.000000000000002, que estouraria o teto para 12), enquanto uma
    # fração genuína de 1 ULP (ex.: 1.0000000000000002) ainda arredonda
    # para cima — nenhum dos dois lados é engolido.
    product = Fraction(repr(shifts)) * scheduled_agents
    return int(math.ceil(product))


def rostered_fractional_agents(scheduled_agents: float, shifts: float) -> float:
    """Multiplica um headcount escalado fracionário pelo fator de turnos, sem arredondar.

    Contraparte fracionária de :func:`rostered_agents` para fluxos
    construídos sobre :func:`scheduled_fractional_agents`, onde toda a
    cadeia permanece fracionária e o arredondamento fica a cargo de quem
    chama.

    Args:
        scheduled_agents (float): Headcount fracionário escalado (ex.: a
            saída de :func:`scheduled_fractional_agents`).
        shifts (float): Operadores por assento ao longo do dia operacional,
            ``>= 1.0``. ``1.0`` retorna ``scheduled_agents`` sem alteração.

    Returns:
        float: Operadores fracionários na escala, sem arredondamento.

    Raises:
        InputValidationError: Se ``shifts`` for menor que ``1.0`` ou
            não-finito, ``scheduled_agents`` for negativo, ou o produto
            estourar o intervalo de float.
    """
    _validate_scheduled_agents(scheduled_agents)
    _validate_shifts(shifts)
    product = float(scheduled_agents) * shifts
    _validate_finite_product(product, scheduled_agents, shifts)
    return product
