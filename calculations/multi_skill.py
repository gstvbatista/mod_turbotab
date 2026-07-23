"""Multi-skill Erlang C dimensioning (Option A: skill partitioning + sharing factor).

This module ships the simplest of three multi-skill approaches described in
the roadmap spec (GitHub issue #15). It models a contact-center where
multiple skill groups (e.g., billing, tech support) may be served by a mix of
dedicated and cross-skilled agent pools.

Three approaches were considered (see Koole 2013; Borst, Mandelbaum & Reiman
2004 for the full discussion):

Option A — implemented here. Treat each skill group as an independent Erlang C
    queue and apply a *sharing factor* to capture the pooling efficiency that
    cross-skilled agents provide. Pure Python, zero third-party dependencies.
    Good for planning estimates; loses accuracy when overlap is large or when
    priority routing meaningfully reshapes the offered load distribution.

Option B — TODO (out of scope for this wish). Monte-Carlo simulation of
    arrivals across skill groups with agents modeled as skill vectors and
    priority-based routing. Most accurate of the three, but the simulation
    harness lives in ``simulation/intraday.py``; integrate after that module
    stabilizes. Doable in pure Python via ``random``.

Option C — TODO (out of scope for this wish). Extended Erlang C (ECCS): an
    analytical approximation built by decomposing the multi-skill system into
    virtual single-skill queues via matrix operations. More accurate than
    Option A, lighter than Option B, but the natural implementation leans on
    numpy for the linear algebra. Defer until either (a) a small pure-Python
    matrix utility lands or (b) the zero-dependency rule is revisited.

The Option A algorithm:

1. For each skill group, compute the baseline single-skill headcount via the
   existing ``agents_required`` function (pure Erlang C, with optional Erlang A
   patience).
2. Detect which skills are served by at least one cross-skilled pool
   (``len(pool["skills"]) > 1`` and ``pool["count"] > 0``).
3. For cross-skilled skills, apply ``sharing_factor`` (default ``0.9``) to the
   baseline. This represents the pooling efficiency gain — fewer agents are
   needed when peak demand from one skill can be absorbed by agents idle on
   another. Smaller ``sharing_factor`` ⇒ larger assumed pooling benefit.
4. Floor the adjusted headcount at ``ceil(offered_traffic) + 1`` to keep
   utilization strictly below 100% per skill.
5. Aggregate totals: naive sum (no sharing), adjusted sum (with sharing),
   savings, and whether the resulting requirement fits the declared
   ``agent_pools``. The fit check solves the underlying assignment problem
   exactly via bipartite max-flow (Edmonds-Karp, pure Python), so
   overlapping shared pools are not double-counted across skills.

The function returns a structured dict (no side effects, no I/O), suitable for
piping into ``--json`` CLI output if the CLI surface picks this up later.
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
            ``{"name": str, "calls_per_interval": float, "aht": int,
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
        raise InputValidationError("skill_groups deve ser uma lista não-vazia.")
    if not isinstance(agent_pools, list) or not agent_pools:
        raise InputValidationError("agent_pools deve ser uma lista não-vazia.")
    if not (0 < sharing_factor <= 1):
        raise InputValidationError("sharing_factor deve estar em (0, 1].")
    if sla < 0 or sla > 1:
        raise InputValidationError("sla deve estar em [0, 1].")
    if service_time < 0:
        raise InputValidationError("service_time deve ser >= 0.")
    if interval <= 0:
        raise InputValidationError("interval deve ser > 0.")
    if patience is not None and patience <= 0:
        raise InputValidationError("patience deve ser > 0 quando informada.")

    seen_names = set()
    for sg in skill_groups:
        for key in ("name", "calls_per_interval", "aht"):
            if key not in sg:
                raise InputValidationError(
                    f"skill_group requer as chaves: name, calls_per_interval, aht. "
                    f"Faltando: {key}."
                )
        if sg["name"] in seen_names:
            raise InputValidationError(f"skill duplicado: {sg['name']}.")
        seen_names.add(sg["name"])
        if sg["calls_per_interval"] < 0:
            raise InputValidationError(
                f"calls_per_interval inválido para '{sg['name']}'."
            )
        if sg["aht"] <= 0:
            raise InputValidationError(
                f"aht deve ser > 0 para '{sg['name']}'."
            )

    for pool in agent_pools:
        if "skills" not in pool or "count" not in pool:
            raise InputValidationError(
                "agent_pool requer as chaves: skills, count."
            )
        if not isinstance(pool["skills"], list) or not pool["skills"]:
            raise InputValidationError(
                "pool.skills deve ser uma lista não-vazia."
            )
        if len(set(pool["skills"])) != len(pool["skills"]):
            raise InputValidationError(
                "pool.skills não pode repetir a mesma skill."
            )
        if pool["count"] < 0:
            raise InputValidationError("pool.count não pode ser negativo.")
        for sk in pool["skills"]:
            if sk not in seen_names:
                raise InputValidationError(
                    f"pool refere skill desconhecida: '{sk}'."
                )

    cross_skilled_set = set()
    for pool in agent_pools:
        if len(pool["skills"]) > 1 and pool["count"] > 0:
            for sk in pool["skills"]:
                cross_skilled_set.add(sk)

    per_skill: list = []
    for sg in skill_groups:
        name: str = sg["name"]
        calls: float = float(sg["calls_per_interval"])
        aht: int = int(sg["aht"])
        offered: float = calls * aht / interval

        if calls == 0:
            # Skill sem volume previsto: demanda zero — sem o HC mínimo de 1
            # que agents_required retorna e sem exigir cobertura por pool.
            baseline_hc: int = 0
        else:
            baseline_hc = agents_required(
                sla=sla,
                service_time=service_time,
                calls_per_interval=calls,
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
