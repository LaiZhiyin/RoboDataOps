"""Portable, provenance-bearing decision exports."""

import csv
import io

from robodataops.models import canonical_json


def _cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def plan_csv(payload: dict) -> bytes:
    context, plan = payload["context"], payload["plan"]
    fields = [
        "plan_id",
        "task_id",
        "task",
        "target",
        "current",
        "new_accepted_episodes",
        "remaining_gap",
        "unit_cost_cents",
        "estimated_cost_cents",
        "capacity",
        "weight",
        "parameter_source",
        "source_kind",
        "repo_id",
        "revision",
        "robot_type",
        "snapshot_id",
        "acceptance_id",
        "targets_id",
        "rule_profile",
        "profile_id",
        "rule_config_json",
        "data_contract_json",
        "document_status",
        "delivery_owner",
        "delivery_date",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fields)
    writer.writeheader()
    for task in payload["tasks"]:
        count = plan["allocation"][task["task_id"]]
        row = {
            "plan_id": payload["plan_id"],
            "task_id": task["task_id"],
            "task": task["label"],
            "target": task["target"],
            "current": task["current"],
            "new_accepted_episodes": count,
            "remaining_gap": task["demand"] - count,
            "unit_cost_cents": task["cost_cents"],
            "estimated_cost_cents": count * task["cost_cents"],
            "capacity": task["capacity"],
            "weight": task["weight"],
            "parameter_source": task["parameter_source"],
            "source_kind": context["source_kind"],
            "snapshot_id": context["snapshot_id"],
            "acceptance_id": context["acceptance_id"],
            "targets_id": context["targets_id"],
            "rule_profile": context["profile"]["version"],
            "delivery_owner": "待指定",
            "delivery_date": "待指定",
            "repo_id": context["repo_id"],
            "revision": context["revision"],
            "robot_type": context["robot_type"],
            "profile_id": context["profile_id"],
            "rule_config_json": canonical_json(context["profile"]),
            "data_contract_json": canonical_json(context["data_contract"]),
            "document_status": "draft: confirm owner, delivery date, units and control mode",
        }
        writer.writerow({key: _cell(value) for key, value in row.items()})
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def plan_json(payload: dict) -> bytes:
    return canonical_json(payload).encode("utf-8")
