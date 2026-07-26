"""Dimensionamento multi-skill Erlang C (Opção A: particionamento de skill + sharing factor).

Este módulo implementa a mais simples das três abordagens multi-skill
descritas no spec do roadmap (issue #15 do GitHub). Modela um contact center
onde múltiplos grupos de skill (ex.: cobrança, suporte técnico) podem ser
atendidos por uma mistura de pools de agentes dedicados e cross-skilled.

Três abordagens foram consideradas (ver Koole 2013; Borst, Mandelbaum & Reiman
2004 para a discussão completa):

Opção A — implementada aqui. Trata cada grupo de skill como uma fila Erlang C
    independente e aplica um *sharing factor* para capturar o ganho de
    eficiência de pooling que os agentes cross-skilled proporcionam. Python
    puro, zero dependências de terceiros. Boa para estimativas de
    planejamento; perde precisão quando o overlap é grande ou quando o
    roteamento por prioridade reformula significativamente a distribuição de
    carga ofertada.

Opção B — TODO (fora do escopo deste wish). Simulação Monte Carlo de chegadas
    entre grupos de skill, com agentes modelados como vetores de skill e
    roteamento por prioridade. A mais precisa das três, mas o harness de
    simulação vive em ``simulation/intraday.py``; integrar após esse módulo
    estabilizar. Viável em Python puro via ``random``.

Opção C — TODO (fora do escopo deste wish). Erlang C estendido (ECCS): uma
    aproximação analítica construída decompondo o sistema multi-skill em
    filas virtuais single-skill via operações matriciais. Mais precisa que a
    Opção A, mais leve que a Opção B, mas a implementação natural depende de
    numpy para a álgebra linear. Adiar até que (a) um utilitário matricial em
    Python puro esteja disponível ou (b) a regra de zero dependências seja
    revisitada.

O algoritmo da Opção A:

1. Para cada grupo de skill, calcula o headcount single-skill baseline via a
   função ``agents_required`` existente (Erlang C puro, com paciência Erlang A
   opcional).
2. Detecta quais skills são atendidas por pelo menos um pool cross-skilled
   (``len(pool["skills"]) > 1`` e ``pool["count"] > 0``).
3. Para skills cross-skilled, aplica o ``sharing_factor`` (padrão ``0.9``) ao
   baseline. Isso representa o ganho de eficiência de pooling — menos
   agentes são necessários quando o pico de demanda de uma skill pode ser
   absorvido por agentes ociosos em outra. ``sharing_factor`` menor ⇒ maior
   benefício de pooling assumido.
4. Estabelece um piso para o headcount ajustado em ``ceil(offered_traffic) + 1``
   para manter a utilização estritamente abaixo de 100% por skill.
5. Agrega os totais: soma ingênua (sem sharing), soma ajustada (com sharing),
   economia, e se o requisito resultante cabe nos ``agent_pools``
   declarados. A checagem de viabilidade resolve o problema de alocação
   subjacente de forma exata via fluxo máximo bipartite (Edmonds-Karp, Python
   puro), de modo que pools compartilhados sobrepostos não sejam contados em
   dobro entre skills.

A função retorna um dict estruturado (sem efeitos colaterais, sem I/O),
adequado para alimentar a saída ``--json`` da CLI caso a superfície da CLI
venha a expor isso futuramente.
"""

import math

from mod_turbotab.agents.capacity import agents_required
from mod_turbotab.exceptions import InputValidationError


def agents_required_multi(
    skill_groups: list,
    agent_pools: list,
    sla: float,
    service_time: int,
    interval: float = 600.0,
    sharing_factor: float = 0.9,
    patience: float = None,
) -> dict:
    """Dimensiona o HC por grupo de skill usando Erlang C particionado.

    Implementa a Opção A do spec (GitHub issue #15):
    cada skill é tratado como uma fila Erlang C independente; skills cobertos
    por pelo menos um pool cross-skilled recebem uma redução proporcional via
    ``sharing_factor`` (efeito de pooling).

    Args:
        skill_groups (list[dict]): Lista de grupos de skill no formato
            ``{"name": str, "contacts_per_interval": float, "aht": int,
            "priority": int (opcional)}``.
        agent_pools (list[dict]): Topologia de cross-skilling, cada item no
            formato ``{"skills": list[str], "count": int}``. Pools com mais de
            uma skill marcam aquelas skills como cross-skilled.
        sla (float): SLA alvo por skill (0 <= x <= 1).
        service_time (int): Tempo alvo de atendimento, em segundos.
        interval (float, optional): Bucket de planejamento, em segundos.
            Padrão 600 (10 minutos).
        sharing_factor (float, optional): Multiplicador aplicado ao baseline HC
            de skills cobertos por pools cross-skilled (0 < x <= 1; valores
            menores = maior ganho de pooling assumido). Padrão 0.9.
        patience (float, optional): Paciência média do cliente em segundos
            (Erlang A). Repassado ao baseline ``agents_required``. Padrão None
            (Erlang C puro).

    Returns:
        dict: Estrutura ``{"per_skill": [...], "totals": {...}}``:

            ``per_skill`` — uma entrada por skill, com:
                - ``name`` (str)
                - ``offered_traffic`` (float, em erlangs)
                - ``baseline_hc`` (int, Erlang C single-skill puro)
                - ``adjusted_hc`` (int, com sharing factor aplicado)
                - ``cross_skilled`` (bool, se algum pool cobre esta skill com
                  outras)
                - ``occupancy_adjusted`` (float, ``A/N`` no HC ajustado)
                - ``eligible_pool_hc`` (int, capacidade dos pools que atendem
                  esta skill)

            ``totals`` — agregados:
                - ``naive_total_hc`` (int, soma dos baselines)
                - ``adjusted_total_hc`` (int, soma dos ajustados)
                - ``savings_hc`` (int, diferença)
                - ``offered_traffic_total`` (float)
                - ``pool_capacity_hc`` (int, soma dos ``count`` dos pools)
                - ``fits_in_pool_capacity`` (bool; viabilidade exata da
                  alocação pools -> skills, decidida por fluxo máximo — pools
                  compartilhados não são contados em dobro entre skills)
                - ``sharing_factor`` (float, ecoado para auditoria)

    Raises:
        InputValidationError: Se as entradas forem inválidas.
    """
    if not isinstance(skill_groups, list) or not skill_groups:
        raise InputValidationError("skill_groups must be a non-empty list.")
    if not isinstance(agent_pools, list) or not agent_pools:
        raise InputValidationError("agent_pools must be a non-empty list.")
    if not (0 < sharing_factor <= 1):
        raise InputValidationError("sharing_factor must be in (0, 1].")
    if sla < 0 or sla > 1:
        raise InputValidationError("sla must be in [0, 1].")
    if service_time < 0:
        raise InputValidationError("service_time must be >= 0.")
    if interval <= 0:
        raise InputValidationError("interval must be > 0.")
    if patience is not None and patience <= 0:
        raise InputValidationError("patience must be > 0 when provided.")

    seen_names = set()
    for sg in skill_groups:
        for key in ("name", "contacts_per_interval", "aht"):
            if key not in sg:
                raise InputValidationError(
                    f"skill_group requires the keys: name, contacts_per_interval, aht. "
                    f"Missing: {key}."
                )
        if sg["name"] in seen_names:
            raise InputValidationError(f"duplicate skill: {sg['name']}.")
        seen_names.add(sg["name"])
        if sg["contacts_per_interval"] < 0:
            raise InputValidationError(
                f"invalid contacts_per_interval for '{sg['name']}'."
            )
        if sg["aht"] <= 0:
            raise InputValidationError(
                f"aht must be > 0 for '{sg['name']}'."
            )

    for pool in agent_pools:
        if "skills" not in pool or "count" not in pool:
            raise InputValidationError(
                "agent_pool requires the keys: skills, count."
            )
        if not isinstance(pool["skills"], list) or not pool["skills"]:
            raise InputValidationError(
                "pool.skills must be a non-empty list."
            )
        if len(set(pool["skills"])) != len(pool["skills"]):
            raise InputValidationError(
                "pool.skills must not repeat the same skill."
            )
        if pool["count"] < 0:
            raise InputValidationError("pool.count must not be negative.")
        for sk in pool["skills"]:
            if sk not in seen_names:
                raise InputValidationError(
                    f"pool references unknown skill: '{sk}'."
                )

    cross_skilled_set = set()
    for pool in agent_pools:
        if len(pool["skills"]) > 1 and pool["count"] > 0:
            for sk in pool["skills"]:
                cross_skilled_set.add(sk)

    per_skill: list = []
    for sg in skill_groups:
        name: str = sg["name"]
        contacts: float = float(sg["contacts_per_interval"])
        aht: int = int(sg["aht"])
        offered: float = contacts * aht / interval

        if contacts == 0:
            # Skill sem volume previsto: demanda zero — sem o HC mínimo de 1
            # que agents_required retorna e sem exigir cobertura por pool.
            baseline_hc: int = 0
        else:
            baseline_hc = agents_required(
                sla=sla,
                service_time=service_time,
                contacts_per_interval=contacts,
                aht=aht,
                interval=interval,
                patience=patience,
            )

        is_cross_skilled: bool = name in cross_skilled_set
        if is_cross_skilled and baseline_hc > 0:
            traffic_floor: int = int(math.ceil(offered)) + 1
            shared_target: int = int(math.ceil(baseline_hc * sharing_factor))
            adjusted_hc: int = max(traffic_floor, shared_target)
        else:
            adjusted_hc = baseline_hc

        occupancy_adjusted: float = (
            offered / adjusted_hc if adjusted_hc > 0 else 0.0
        )

        # Capacidade elegível: soma dos pools que atendem este skill (campo
        # de diagnóstico; a viabilidade real é decidida por fluxo máximo).
        eligible_hc: int = sum(
            p["count"] for p in agent_pools if name in p["skills"]
        )

        per_skill.append(
            {
                "name": name,
                "offered_traffic": offered,
                "baseline_hc": baseline_hc,
                "adjusted_hc": adjusted_hc,
                "cross_skilled": is_cross_skilled,
                "occupancy_adjusted": occupancy_adjusted,
                "eligible_pool_hc": eligible_hc,
            }
        )

    naive_total: int = sum(s["baseline_hc"] for s in per_skill)
    adjusted_total: int = sum(s["adjusted_hc"] for s in per_skill)
    offered_total: float = sum(s["offered_traffic"] for s in per_skill)
    pool_capacity: int = sum(p["count"] for p in agent_pools)

    return {
        "per_skill": per_skill,
        "totals": {
            "naive_total_hc": naive_total,
            "adjusted_total_hc": adjusted_total,
            "savings_hc": naive_total - adjusted_total,
            "offered_traffic_total": offered_total,
            "pool_capacity_hc": pool_capacity,
            "fits_in_pool_capacity": _pools_cover_requirement(per_skill, agent_pools),
            "sharing_factor": sharing_factor,
        },
    }


def _pools_cover_requirement(per_skill: list, agent_pools: list) -> bool:
    """Decide se os pools cobrem o HC ajustado via fluxo máximo (Edmonds-Karp).

    Modela o problema de alocação como um grafo bipartite: fonte -> pool
    (capacidade ``count``), pool -> skill que ele atende (capacidade
    ilimitada) e skill -> sumidouro (capacidade ``adjusted_hc``). Os pools
    cobrem o requisito se, e somente se, o fluxo máximo igualar a demanda
    total — checagens agregadas ou por skill deixam passar déficits em
    subconjuntos sobrepostos (ex.: duas skills de 10 disputando um único
    pool compartilhado de 10).
    """
    demand_total: int = sum(s["adjusted_hc"] for s in per_skill)
    if demand_total == 0:
        return True

    # Nós: 0 = fonte, 1..P = pools, P+1..P+S = skills, último = sumidouro.
    source: int = 0
    pool_base: int = 1
    skill_base: int = pool_base + len(agent_pools)
    sink: int = skill_base + len(per_skill)
    skill_index = {s["name"]: skill_base + i for i, s in enumerate(per_skill)}

    capacity: dict = {}

    def _add_edge(u: int, v: int, cap: int) -> None:
        capacity.setdefault(u, {})[v] = capacity.get(u, {}).get(v, 0) + cap
        capacity.setdefault(v, {}).setdefault(u, 0)

    for i, pool in enumerate(agent_pools):
        _add_edge(source, pool_base + i, int(pool["count"]))
        for sk in pool["skills"]:
            _add_edge(pool_base + i, skill_index[sk], int(pool["count"]))
    for s in per_skill:
        _add_edge(skill_index[s["name"]], sink, int(s["adjusted_hc"]))

    max_flow: int = 0
    while True:
        # BFS por caminho aumentante.
        parent = {source: None}
        queue = [source]
        while queue and sink not in parent:
            u = queue.pop(0)
            for v, cap in capacity.get(u, {}).items():
                if cap > 0 and v not in parent:
                    parent[v] = u
                    queue.append(v)
        if sink not in parent:
            break
        bottleneck = demand_total
        v = sink
        while parent[v] is not None:
            u = parent[v]
            bottleneck = min(bottleneck, capacity[u][v])
            v = u
        v = sink
        while parent[v] is not None:
            u = parent[v]
            capacity[u][v] -= bottleneck
            capacity[v][u] += bottleneck
            v = u
        max_flow += bottleneck

    return max_flow >= demand_total
