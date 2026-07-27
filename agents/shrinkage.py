"""
Ajustes de shrinkage e absenteísmo para o dimensionamento de escala.

Erlang C calcula o número de agentes necessários **ao telefone**. O shrinkage
cobre a diferença entre "agentes ao telefone" e "agentes para escalar",
aplicando a correção padrão de workforce management:

    HC_escalado = HC_requerido / (1 - shrinkage)

Este módulo implementa a **Opção A** (ajuste pós-cálculo) do spec da issue
#17: a matemática Erlang principal não muda; o shrinkage é aplicado por cima.
"""

import math

from mod_turbotab.agents.capacity import agents_required
from mod_turbotab.exceptions import InputValidationError

# Tolerância para divisões exatas que estouram o teto por erro de float
# (ex.: 1 / (1 - 0.8) = 5.000000000000001 arredondaria 5 para 6). Mesmo
# padrão do _OCCUPANCY_EPSILON em agents/capacity.py.
_SHRINKAGE_EPSILON: float = 1e-9


def _validate_agents_on_phone(agents_on_phone: float) -> None:
    """Rejeita headcounts ao telefone negativos ou não-finitos.

    NaN compara falso com qualquer limite, então uma checagem apenas de
    negativo deixaria NaN (e inf) passarem e se propagarem para os
    resultados e para a saída JSON.
    """
    if not math.isfinite(agents_on_phone) or agents_on_phone < 0:
        raise InputValidationError(
            "agents_on_phone must be a finite value >= 0. "
            f"Received: {agents_on_phone}."
        )


def _validate_finite_quotient(quotient: float, agents_on_phone: float, shrinkage: float) -> None:
    """Rejeita quocientes que estouram o intervalo de float.

    Um headcount finito dividido por ``1 - shrinkage`` pequeno pode estourar
    para ``inf`` (ex.: 6e307 agentes com shrinkage 0.9); sem esta checagem a
    cadeia fracionária emitiria ``Infinity`` na saída JSON — que não é JSON
    válido — e a inteira morreria com OverflowError sem tratamento no ceil.
    Mesmo padrão do _validate_finite_product em agents/roster.py.
    """
    if not math.isfinite(quotient):
        # :g compacta o headcount na mensagem — no caminho inteiro ele pode
        # ser um int de centenas de dígitos.
        raise InputValidationError(
            "agents_on_phone / (1 - shrinkage) must be finite. "
            f"Received: agents_on_phone={agents_on_phone:g}, shrinkage={shrinkage}."
        )


def _validate_shrinkage(shrinkage: float) -> None:
    """Rejeita fatores de shrinkage inválidos.

    Shrinkage deve ser um valor finito em ``[0.0, 1.0)``. Um valor de
    ``1.0`` implicaria que a força de trabalho está inteiramente
    indisponível (divisão por zero); valores negativos não fazem sentido.
    Valores não-finitos (NaN/inf) escapam das checagens de intervalo — NaN
    compara falso com tudo — e se propagariam para os resultados,
    produzindo saída JSON inválida.
    """
    if not math.isfinite(shrinkage) or shrinkage < 0 or shrinkage >= 1.0:
        raise InputValidationError(
            "Shrinkage must be in the range [0.0, 1.0). "
            f"Received: {shrinkage}."
        )


def scheduled_agents(agents_on_phone: int, shrinkage: float) -> int:
    """Infla ``agents_on_phone`` pelo fator de shrinkage.

    Args:
        agents_on_phone (int): Número de agentes necessários ao telefone
            (ex.: a saída de :func:`agents_required`).
        shrinkage (float): Fração do tempo pago indisponível para atender
            chamadas, em ``[0.0, 1.0)``. ``0.0`` retorna ``agents_on_phone``
            sem alteração.

    Returns:
        int: Headcount a escalar, arredondado para cima.

    Raises:
        InputValidationError: Se ``shrinkage`` estiver fora de
            ``[0.0, 1.0)`` ou ``agents_on_phone`` for negativo.
    """
    _validate_agents_on_phone(agents_on_phone)
    _validate_shrinkage(shrinkage)
    if shrinkage == 0.0:
        return int(agents_on_phone)
    quotient: float = agents_on_phone / (1.0 - shrinkage)
    _validate_finite_quotient(quotient, agents_on_phone, shrinkage)
    return int(math.ceil(quotient - _SHRINKAGE_EPSILON))


def scheduled_fractional_agents(agents_on_phone: float, shrinkage: float) -> float:
    """Infla um headcount fracionário pelo fator de shrinkage, sem arredondar.

    Contraparte fracionária de :func:`scheduled_agents` para fluxos
    construídos sobre :func:`fractional_agents`, onde toda a cadeia
    permanece fracionária e o arredondamento fica a cargo de quem chama.

    Args:
        agents_on_phone (float): Agentes fracionários necessários ao
            telefone (ex.: a saída de :func:`fractional_agents`).
        shrinkage (float): Fração do tempo pago indisponível para atender
            chamadas, em ``[0.0, 1.0)``. ``0.0`` retorna ``agents_on_phone``
            sem alteração.

    Returns:
        float: Headcount fracionário a escalar, sem arredondamento.

    Raises:
        InputValidationError: Se ``shrinkage`` estiver fora de
            ``[0.0, 1.0)`` ou ``agents_on_phone`` for negativo.
    """
    _validate_agents_on_phone(agents_on_phone)
    _validate_shrinkage(shrinkage)
    quotient: float = float(agents_on_phone) / (1.0 - shrinkage)
    _validate_finite_quotient(quotient, agents_on_phone, shrinkage)
    return quotient


def shrinkage_factor(
    breaks: float = 0.0,
    training: float = 0.0,
    meetings: float = 0.0,
    absenteeism: float = 0.0,
    system_downtime: float = 0.0,
    other: float = 0.0,
) -> float:
    """Combina componentes individuais de shrinkage em um único fator.

    Os componentes são aditivos — representam fatias disjuntas do tempo
    pago fora do telefone. Cada componente deve estar em ``[0.0, 1.0)`` e a
    soma deve permanecer estritamente abaixo de ``1.0``.

    Args:
        breaks (float): Pausas remuneradas.
        training (float): Tempo de treinamento.
        meetings (float): Reuniões de equipe, 1:1s, etc.
        absenteeism (float): Ausências não planejadas.
        system_downtime (float): Tempo perdido por indisponibilidade de
            sistema/ferramentas.
        other (float): Qualquer componente adicional não listado acima.

    Returns:
        float: Shrinkage combinado em ``[0.0, 1.0)``.

    Raises:
        InputValidationError: Se algum componente for negativo ou o total
            atingir ``1.0``.
    """
    components = {
        "breaks": breaks,
        "training": training,
        "meetings": meetings,
        "absenteeism": absenteeism,
        "system_downtime": system_downtime,
        "other": other,
    }
    for name, value in components.items():
        if value < 0:
            raise InputValidationError(
                f"Shrinkage component '{name}' must be >= 0. "
                f"Received: {value}."
            )
    total = sum(components.values())
    _validate_shrinkage(total)
    return total


def agents_required_with_shrinkage(
    sla: float,
    service_time: int,
    contacts_per_interval: float,
    aht: int,
    shrinkage: float = 0.0,
    interval: float = 600.0,
    patience: float = None,
    max_occupancy: float = None,
) -> int:
    """Calcula o headcount escalado, aplicando shrinkage sobre a saída Erlang C.

    Equivale a :func:`agents_required` seguido de :func:`scheduled_agents`.
    Com ``shrinkage=0.0`` (padrão) o resultado é idêntico a
    ``agents_required(...)``.

    Args:
        sla (float): Nível de serviço alvo (ex.: ``0.80`` para 80%).
        service_time (int): Tempo alvo de atendimento, em segundos.
        contacts_per_interval (float): Chegadas por intervalo de
            planejamento.
        aht (int): Duração média do contato, em segundos.
        shrinkage (float, optional): Shrinkage combinado em ``[0.0, 1.0)``.
            Padrão ``0.0`` (sem ajuste).
        interval (float, optional): Intervalo de planejamento em segundos.
            Padrão ``600`` (10 minutos), consistente com o resto da
            biblioteca.
        patience (float, optional): Paciência média para Erlang A. ``None``
            usa Erlang C puro.
        max_occupancy (float, optional): Ocupação máxima tolerada por
            agente, repassada a :func:`agents_required`. ``None`` desativa
            o teto de ocupação.

    Returns:
        int: Número de agentes a escalar.

    Raises:
        InputValidationError: Se ``shrinkage`` for inválido ou algum dos
            parâmetros subjacentes falhar na validação de
            :func:`agents_required`.
        CalculationError: Se o cálculo Erlang subjacente falhar.
    """
    _validate_shrinkage(shrinkage)
    on_phone = agents_required(
        sla,
        service_time,
        contacts_per_interval,
        aht,
        interval=interval,
        patience=patience,
        max_occupancy=max_occupancy,
    )
    return scheduled_agents(on_phone, shrinkage)
