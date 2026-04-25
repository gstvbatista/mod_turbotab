"""Command-line interface for mod_turbotab."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from mod_turbotab import __version__
from mod_turbotab.agents.capacity import (
    agents_asa,
    agents_required,
    asa,
    call_capacity,
    fractional_agents,
    fractional_call_capacity,
    nb_agents,
)
from mod_turbotab.calculations.erlang import (
    engset_b,
    erlang_a,
    erlang_b,
    erlang_b_ext,
    erlang_c,
)
from mod_turbotab.calculations.traffic import traffic
from mod_turbotab.exceptions import CalculationError, InputValidationError
from mod_turbotab.queues.queues import (
    queue_size,
    queue_time,
    queued,
    service_time,
    sla_metric,
)
from mod_turbotab.trunks.trunks import number_trunks, trunks_required


DEFAULT_INTERVAL = 600.0


def main(argv: list[str] | None = None) -> int:
    """Run the turbotab command-line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    try:
        payload = args.handler(args)
    except (InputValidationError, CalculationError, ValueError, ZeroDivisionError) as exc:
        print(f"turbotab: error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print(_format_text(payload))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="turbotab",
        description=(
            "TurboTable-style contact-center, Erlang, queue, and trunk "
            "capacity calculations."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    categories = parser.add_subparsers(dest="category", metavar="category")
    _add_agents_commands(categories)
    _add_queues_commands(categories)
    _add_erlang_commands(categories)
    _add_traffic_commands(categories)
    _add_trunks_commands(categories)
    return parser


def _add_agents_commands(categories: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = categories.add_parser("agents", help="Staffing and agent capacity calculations.")
    commands = parser.add_subparsers(dest="agents_command", metavar="command")

    required = commands.add_parser("required", help="Calculate agents required for a target SLA.")
    _add_output_arg(required)
    _add_sla_arg(required)
    _add_service_time_arg(required)
    _add_calls_arg(required)
    _add_aht_arg(required)
    _add_interval_arg(required)
    _add_patience_arg(required)
    _set_handler(required, "agents.required", "agents", "agents", agents_required)

    asa_parser = commands.add_parser("asa", help="Calculate average speed of answer in seconds.")
    _add_output_arg(asa_parser)
    _add_agents_arg(asa_parser)
    _add_calls_arg(asa_parser)
    _add_aht_arg(asa_parser)
    _add_interval_arg(asa_parser)
    _add_patience_arg(asa_parser)
    _set_handler(asa_parser, "agents.asa", "seconds", "asa", asa)

    asa_required = commands.add_parser("asa-required", help="Calculate agents required for a target ASA.")
    _add_output_arg(asa_required)
    asa_required.add_argument("--asa-target", type=float, required=True, help="Target ASA in seconds.")
    _add_calls_arg(asa_required)
    _add_aht_arg(asa_required)
    _add_interval_arg(asa_required)
    _set_handler(asa_required, "agents.asa_required", "agents", "agents", agents_asa)

    nb_parser = commands.add_parser("nb-agents", help="Calculate agents required from average ASA and AHT.")
    _add_output_arg(nb_parser)
    _add_calls_arg(nb_parser)
    nb_parser.add_argument("--avg-sa", type=float, required=True, help="Average speed of answer in seconds.")
    nb_parser.add_argument("--avg-ht", type=int, required=True, help="Average handle time in seconds.")
    _add_interval_arg(nb_parser)
    _set_handler(nb_parser, "agents.nb_agents", "agents", "agents", nb_agents)

    capacity = commands.add_parser("capacity", help="Calculate maximum calls for a staffed SLA target.")
    _add_output_arg(capacity)
    capacity.add_argument("--no-agents", type=float, required=True, help="Available agents.")
    _add_sla_arg(capacity)
    _add_service_time_arg(capacity)
    _add_aht_arg(capacity)
    _add_interval_arg(capacity)
    _set_handler(capacity, "agents.capacity", "calls_per_interval", "call_capacity", call_capacity)

    fractional_required = commands.add_parser(
        "fractional-required",
        help="Calculate fractional agents required for a target SLA.",
    )
    _add_output_arg(fractional_required)
    _add_sla_arg(fractional_required)
    _add_service_time_arg(fractional_required)
    _add_calls_arg(fractional_required)
    _add_aht_arg(fractional_required)
    _add_interval_arg(fractional_required)
    _add_patience_arg(fractional_required)
    _set_handler(
        fractional_required,
        "agents.fractional_required",
        "agents",
        "fractional_agents",
        fractional_agents,
    )

    fractional_capacity = commands.add_parser(
        "fractional-capacity",
        help="Calculate maximum calls for a fractional staffed SLA target.",
    )
    _add_output_arg(fractional_capacity)
    fractional_capacity.add_argument("--no-agents", type=float, required=True, help="Available fractional agents.")
    _add_sla_arg(fractional_capacity)
    _add_service_time_arg(fractional_capacity)
    _add_aht_arg(fractional_capacity)
    _add_interval_arg(fractional_capacity)
    _set_handler(
        fractional_capacity,
        "agents.fractional_capacity",
        "calls_per_interval",
        "fractional_call_capacity",
        fractional_call_capacity,
    )


def _add_queues_commands(categories: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = categories.add_parser("queues", help="Queue wait, size, and SLA metrics.")
    commands = parser.add_subparsers(dest="queues_command", metavar="command")

    queued_parser = commands.add_parser("queued", help="Calculate percentage of calls that queue.")
    _add_output_arg(queued_parser)
    _add_agents_arg(queued_parser)
    _add_calls_arg(queued_parser)
    _add_aht_arg(queued_parser)
    _add_interval_arg(queued_parser)
    _add_patience_arg(queued_parser)
    _set_handler(queued_parser, "queues.queued", "ratio", "queued", queued)

    size_parser = commands.add_parser("size", help="Calculate average queue size in calls.")
    _add_output_arg(size_parser)
    _add_agents_arg(size_parser)
    _add_calls_arg(size_parser)
    _add_aht_arg(size_parser)
    _add_interval_arg(size_parser)
    _add_patience_arg(size_parser)
    _set_handler(size_parser, "queues.size", "calls", "queue_size", queue_size)

    time_parser = commands.add_parser("time", help="Calculate average queue wait time in seconds.")
    _add_output_arg(time_parser)
    _add_agents_arg(time_parser)
    _add_calls_arg(time_parser)
    _add_aht_arg(time_parser)
    _add_interval_arg(time_parser)
    _add_patience_arg(time_parser)
    _set_handler(time_parser, "queues.time", "seconds", "queue_time", queue_time)

    service_parser = commands.add_parser("service-time", help="Calculate answer time needed for a target SLA.")
    _add_output_arg(service_parser)
    _add_agents_arg(service_parser)
    _add_sla_arg(service_parser)
    _add_calls_arg(service_parser)
    _add_aht_arg(service_parser)
    _add_interval_arg(service_parser)
    _add_patience_arg(service_parser)
    _set_handler(service_parser, "queues.service_time", "seconds", "service_time", service_time)

    sla_parser = commands.add_parser("sla", help="Calculate achieved SLA for staffing and target answer time.")
    _add_output_arg(sla_parser)
    _add_agents_arg(sla_parser)
    sla_parser.add_argument("--service-time", dest="service_time_val", type=float, required=True, help="Target answer time in seconds.")
    _add_calls_arg(sla_parser)
    _add_aht_arg(sla_parser)
    _add_interval_arg(sla_parser)
    _add_patience_arg(sla_parser)
    _set_handler(sla_parser, "queues.sla", "ratio", "sla_metric", sla_metric)


def _add_erlang_commands(categories: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = categories.add_parser("erlang", help="Erlang B, C, A, and Engset calculations.")
    commands = parser.add_subparsers(dest="erlang_command", metavar="command")

    b_parser = commands.add_parser("b", help="Calculate Erlang B blocking probability.")
    _add_output_arg(b_parser)
    _add_servers_arg(b_parser)
    _add_intensity_arg(b_parser)
    _set_handler(b_parser, "erlang.b", "ratio", "blocking_probability", erlang_b)

    b_ext_parser = commands.add_parser("b-ext", help="Calculate retry-aware extended Erlang B.")
    _add_output_arg(b_ext_parser)
    _add_servers_arg(b_ext_parser)
    _add_intensity_arg(b_ext_parser)
    b_ext_parser.add_argument("--retry", type=float, required=True, help="Retry ratio, for example 0.1 for 10%%.")
    _set_handler(b_ext_parser, "erlang.b_ext", "ratio", "blocking_probability", erlang_b_ext)

    c_parser = commands.add_parser("c", help="Calculate Erlang C queueing probability.")
    _add_output_arg(c_parser)
    _add_servers_arg(c_parser)
    _add_intensity_arg(c_parser)
    _set_handler(c_parser, "erlang.c", "ratio", "queue_probability", erlang_c)

    a_parser = commands.add_parser("a", help="Calculate Erlang A abandonment metrics.")
    _add_output_arg(a_parser)
    _add_servers_arg(a_parser)
    _add_intensity_arg(a_parser)
    _add_patience_arg(a_parser, required=True)
    _add_aht_arg(a_parser)
    a_parser.add_argument("--target-time", type=float, default=None, help="Optional SLA target time in seconds.")
    a_parser.set_defaults(handler=_handle_erlang_a, calculation="erlang.a")

    engset_parser = commands.add_parser("engset-b", help="Calculate Engset B blocking probability.")
    _add_output_arg(engset_parser)
    _add_servers_arg(engset_parser)
    engset_parser.add_argument("--events", type=float, required=True, help="Number of finite sources/events.")
    _add_intensity_arg(engset_parser)
    _set_handler(engset_parser, "erlang.engset_b", "ratio", "blocking_probability", engset_b)


def _add_traffic_commands(categories: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = categories.add_parser("traffic", help="Traffic intensity inversion helpers.")
    commands = parser.add_subparsers(dest="traffic_command", metavar="command")

    intensity_parser = commands.add_parser("intensity", help="Calculate traffic intensity for servers and blocking.")
    _add_output_arg(intensity_parser)
    _add_servers_arg(intensity_parser)
    intensity_parser.add_argument("--blocking", type=float, required=True, help="Target blocking probability.")
    _set_handler(intensity_parser, "traffic.intensity", "erlangs", "traffic_intensity", traffic)


def _add_trunks_commands(categories: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = categories.add_parser("trunks", help="Telephony trunk sizing calculations.")
    commands = parser.add_subparsers(dest="trunks_command", metavar="command")

    required_parser = commands.add_parser("required", help="Calculate trunks required for call volume.")
    _add_output_arg(required_parser)
    _add_agents_arg(required_parser)
    _add_calls_arg(required_parser)
    _add_aht_arg(required_parser)
    _add_interval_arg(required_parser)
    _set_handler(required_parser, "trunks.required", "trunks", "trunks_required", trunks_required)

    number_parser = commands.add_parser("number", help="Calculate trunks required for servers and traffic intensity.")
    _add_output_arg(number_parser)
    _add_servers_arg(number_parser)
    _add_intensity_arg(number_parser)
    _set_handler(number_parser, "trunks.number", "trunks", "number_trunks", number_trunks)


def _add_output_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit deterministic JSON for agent/tool use.")


def _add_agents_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agents", type=float, required=True, help="Number of agents.")


def _add_servers_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--servers", type=float, required=True, help="Number of servers, agents, or trunks.")


def _add_intensity_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--intensity", type=float, required=True, help="Offered traffic intensity in erlangs.")


def _add_sla_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sla", type=float, required=True, help="SLA ratio, for example 0.80 for 80%%.")


def _add_service_time_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--service-time", type=int, required=True, help="Target answer time in seconds.")


def _add_calls_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--calls-per-interval", type=float, required=True, help="Arrival calls per planning interval.")


def _add_aht_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--aht", type=int, required=True, help="Average handle time in seconds.")


def _add_interval_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="Planning interval in seconds. Default: 600 seconds.",
    )


def _add_patience_arg(parser: argparse.ArgumentParser, required: bool = False) -> None:
    parser.add_argument(
        "--patience",
        type=float,
        default=None,
        required=required,
        help="Average caller patience in seconds for Erlang A calculations.",
    )


def _set_handler(
    parser: argparse.ArgumentParser,
    calculation: str,
    unit: str,
    result_name: str,
    func: Callable[..., Any],
) -> None:
    parser.set_defaults(
        handler=lambda args: _handle_function(args, calculation, unit, result_name, func),
        calculation=calculation,
    )


def _handle_function(
    args: argparse.Namespace,
    calculation: str,
    unit: str,
    result_name: str,
    func: Callable[..., Any],
) -> dict[str, Any]:
    result = func(**_function_inputs(args))
    return {
        "schema_version": "1.0",
        "calculation": calculation,
        "inputs": _public_inputs(args),
        "result": {
            "name": result_name,
            "value": result,
            "unit": unit,
        },
    }


def _handle_erlang_a(args: argparse.Namespace) -> dict[str, Any]:
    inputs = _function_inputs(args, exclude={"target_time"})
    metrics = erlang_a(**inputs)
    result: dict[str, Any] = {
        "probability_waiting": metrics["pw"],
        "asa": metrics["asa"],
        "abandon_rate": metrics["abandon_rate"],
    }
    if args.target_time is not None:
        result["sla"] = metrics["sla"](args.target_time)
        result["target_time"] = args.target_time
    return {
        "schema_version": "1.0",
        "calculation": "erlang.a",
        "inputs": _public_inputs(args),
        "result": {
            "name": "erlang_a_metrics",
            "value": result,
            "unit": "mixed",
        },
    }


def _function_inputs(args: argparse.Namespace, exclude: set[str] | None = None) -> dict[str, Any]:
    excluded = {
        "handler",
        "json",
        "category",
        "calculation",
        "agents_command",
        "queues_command",
        "erlang_command",
        "traffic_command",
        "trunks_command",
    }
    if exclude:
        excluded.update(exclude)
    return {
        key: value
        for key, value in vars(args).items()
        if key not in excluded and value is not None
    }


def _public_inputs(args: argparse.Namespace, exclude: set[str] | None = None) -> dict[str, Any]:
    aliases = {
        "no_agents": "agents",
        "service_time_val": "service_time",
    }
    inputs = _function_inputs(args, exclude=exclude)
    return {
        aliases.get(key, key): value
        for key, value in inputs.items()
    }


def _format_text(payload: dict[str, Any]) -> str:
    result = payload["result"]
    value = result["value"]
    if isinstance(value, dict):
        details = ", ".join(f"{key}={val}" for key, val in value.items())
        rendered_value = details
    else:
        rendered_value = str(value)
    return f"{payload['calculation']}: {result['name']}={rendered_value} {result['unit']}"


if __name__ == "__main__":
    raise SystemExit(main())
