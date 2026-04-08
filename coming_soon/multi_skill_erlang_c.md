# Multi-Skill Erlang C

## Problem

The current library models single-queue, single-skill operations only. Real contact centers often have agents handling multiple skill groups (e.g., billing + tech support), or queues that overflow into shared agent pools.

## What It Solves

- Dimensioning for operations where agents serve more than one queue
- Modeling skill-based routing (SBR) where calls route to the best-fit agent, then overflow
- More accurate HC requirements when skills overlap

## Mathematical Approach

Multi-skill Erlang is significantly more complex than single-skill. Two main approaches:

### Option A: Erlang C with skill partitioning
- Treat each skill as independent Erlang C queue
- Apply a sharing factor to account for cross-skilled agents
- Simpler, less accurate, good for planning estimates

### Option B: Simulation-based
- Monte Carlo simulation of arrivals across skill groups
- Agents with skill vectors, priority-based routing
- More accurate, computationally heavier

### Option C: Extended Erlang C (ECCS model)
- Analytical approximation for multi-skill environments
- Based on decomposition into virtual single-skill queues
- Middle ground between A and B

## API Surface (Draft)

```python
# Skill group definition
skill_group = {
    "name": "billing",
    "calls_per_interval": 50,
    "aht": 240,
    "priority": 1
}

# Agent pool definition
agent_pool = {
    "skills": ["billing", "tech_support"],
    "count": 15
}

# Multi-skill dimensioning
agents_required_multi(
    skill_groups: list[dict],
    agent_pools: list[dict],
    sla: float,
    service_time: int
) -> dict  # HC per skill group
```

## Dependencies

- May need numpy for matrix operations (breaking the zero-dependency principle)
- Alternative: pure Python with performance trade-off

## Complexity

High. This is a significant feature that changes the library's scope. Recommend implementing after the core is robust and well-tested.

## References

- Koole, G. (2013). Call Center Optimization. MG Books.
- Borst, S., Mandelbaum, A., Reiman, M. (2004). Dimensioning Large Call Centers.
