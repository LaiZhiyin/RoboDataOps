"""Reconcile a returned batch without crediting baseline/duplicate episodes twice."""

from collections import Counter

from robodataops.contracts import REQUIRED_FIELDS, action_contract
from robodataops.errors import ValidationError
from robodataops.metrics import episode_states
from robodataops.models import canonical_json


def reconcile(payload, batch, audit, reviews, previous):
    context = payload["context"]
    if batch.repo_id != context["repo_id"]:
        raise ValidationError(
            "到货来源与原方案不同，需要先提供明确任务和源身份映射；当前仅支持同一数据源"
        )
    if audit.profile.profile_id != context["profile_id"]:
        raise ValidationError("到货检查口径与原方案不同，请使用原规则配置")
    expected_contract = context["data_contract"]
    expected_features = {
        key: {name: expected_contract["features"][key][name] for name in ("dtype", "shape")}
        for key in REQUIRED_FIELDS
    }
    incoming_features = {
        key: {name: batch.info["features"][key][name] for name in ("dtype", "shape")}
        for key in REQUIRED_FIELDS
    }
    if (
        batch.info.get("robot_type", "unknown") != context["robot_type"]
        or batch.info["fps"] != expected_contract["fps"]
        or incoming_features != expected_features
        or context["data_contract"]["action_semantics"] != action_contract(batch.manifest)
    ):
        raise ValidationError(
            "到货平台、FPS 或必需字段契约与原方案不同，需要显式映射后重新制定计划"
        )
    for task in payload["tasks"]:
        if batch.tasks.get(task["task_id"]) != task["label"]:
            raise ValidationError("任务定义发生变化，不能静默归入旧方案")
    seen = {
        canonical_json([batch.repo_id, source_id]) for source_id in context["existing_source_ids"]
    }
    seen.update(key for receipt in previous for key in receipt["new_source_keys"])
    previously_credited = Counter()
    for receipt in previous:
        if receipt["plan_id"] == payload["plan_id"]:
            for row in receipt["items"]:
                previously_credited[row["task_id"]] += row["credited"]
    available = Counter()
    source_keys = []
    excluded = 0
    states = episode_states(batch, audit, reviews)
    for row in states:
        key = canonical_json([batch.repo_id, row["episode_index"]])
        if key in seen:
            excluded += 1
        elif row["status"] == "accepted":
            source_keys.append(key)
            available[row["task_id"]] += 1
    items = []
    for task in payload["tasks"]:
        task_id = task["task_id"]
        requested = payload["plan"]["allocation"][task_id]
        remaining = max(0, requested - previously_credited[task_id])
        credited = min(available[task_id], remaining)
        items.append(
            {
                "task_id": task_id,
                "task": task["label"],
                "planned": requested,
                "previously_credited": previously_credited[task_id],
                "new_accepted": available[task_id],
                "credited": credited,
                "outstanding": remaining - credited,
            }
        )
    return {
        "plan_id": payload["plan_id"],
        "snapshot_id": batch.snapshot_id,
        "source_kind": batch.source_kind,
        "run_id": audit.run_id,
        "profile_id": audit.profile.profile_id,
        "items": items,
        "received": len(states),
        "baseline_or_duplicate": excluded,
        "new_source_keys": source_keys,
        "notice": "按原验收口径核对到货，未计真实费用或策略收益；合成数据只验证回流流程。",
    }
