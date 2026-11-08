"""Local operator workbench. Use ROBODATAOPS_DEMO_MODE=1 for isolated sessions."""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from robodataops.demo import default_targets, generate_demo
from robodataops.errors import RoboDataOpsError, ValidationError
from robodataops.export import plan_csv, plan_json
from robodataops.ingest import load_batch, safe_path
from robodataops.metrics import STATUS_LABELS, context_for, coverage, episode_states, planning_tasks
from robodataops.models import RuleProfile, Target, canonical_json, digest, jsonable
from robodataops.planning import compare_plans, money_to_cents
from robodataops.quality import audit_batch
from robodataops.store import Store

PROJECT = Path(__file__).resolve().parent
STRATEGY_NAMES = {"equal": "等额预算", "greedy": "收益成本比贪心", "optimal": "整数优化"}
DECISIONS = {
    "confirmed": "确认问题并排除",
    "dismissed": "驳回标记，保留数据",
    "deferred": "暂缓，等待更多证据",
}
PLAN_STATUS = {
    "optimal": "已证明最优",
    "heuristic": "基线可行方案",
    "feasible": "可行，未证明最优",
    "no_gap": "当前无缺口",
    "no_solution": "限时未返回方案",
    "infeasible": "报告不可行，需诊断",
    "error": "求解错误",
}

st.set_page_config(page_title="RoboDataOps · 数据决策工作台", page_icon="◫", layout="wide")
st.markdown(
    """
<style>
html, body, [data-testid="stMarkdownContainer"], [data-testid="stMetricValue"], label, input, button {font-family:"Avenir Next","PingFang SC","Noto Sans CJK SC",sans-serif;}
.block-container {padding:4.5rem 3rem 3rem; max-width:1600px;}
h1,h2,h3 {font-weight:650 !important; letter-spacing:-.035em;}
h1 {font-size:2.15rem !important; margin-bottom:.15rem;}
h2 {font-size:1.35rem !important; margin-top:1.4rem;}
[data-testid="stSidebar"] {background:#132f33;}
[data-testid="stSidebar"] {color:#e5eeeb;}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"], [data-testid="stSidebar"] label {color:#e5eeeb;}
[data-testid="stSidebar"] button {background:#254a4d;color:#e5eeeb;border-color:#476365;}
[data-testid="stSidebar"] input {color:#193434;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#193434;}
[data-testid="stSidebar"] hr {border-color:#385055;}
[data-testid="stMetric"] {border-top:2px solid #cbd9d1; padding:1rem 0 .6rem;}
[data-testid="stMetricValue"] {font-family:"Avenir Next","PingFang SC",sans-serif; font-size:2.1rem;}
.brand {font-family:"Avenir Next",sans-serif; font-size:1.65rem; font-weight:700; letter-spacing:-.06em; margin:0 0 .1rem;}
.brand-sub {font-size:.72rem; letter-spacing:.13em; color:#a5c7ba !important; margin-bottom:2.3rem;}
.eyebrow {font-family:"SFMono-Regular",Consolas,monospace; font-size:.73rem; color:#628078; letter-spacing:.14em; margin-bottom:.6rem;}
.step-strip {border-top:1px solid #d5dfd8;border-bottom:1px solid #d5dfd8;padding:.8rem 0;margin:1rem 0 1.7rem;color:#628078;font-size:.8rem;letter-spacing:.03em;}
.source-pill {display:inline-block;color:#91541e;background:#f4e8d5;font-size:.72rem;padding:.22rem .6rem;border-radius:3px;font-weight:600;}
.source-public {color:#17674d;background:#dcefe4;}
[data-testid="stDataFrame"] {border:1px solid #dbe4dd; border-radius:4px;}
.stButton > button, .stDownloadButton > button {border-radius:4px; font-weight:600;}
[data-testid="stCaptionContainer"] {color:#638078;}
[data-testid="stCaptionContainer"] p {color:#4f7065;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"], [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#adc7bf;}
[data-testid="stAppDeployButton"], .stAppDeployButton {display:none;}
[data-testid="stForm"] {border:1px solid #d5dfd8; border-radius:4px;}
@media (max-width:800px) {.block-container {padding:4rem 1rem 1.5rem;} h1 {font-size:1.7rem !important;}}
</style>
""",
    unsafe_allow_html=True,
)


def store() -> Store:
    if "_store" not in st.session_state:
        demo_mode = os.environ.get("ROBODATAOPS_DEMO_MODE") == "1"
        path = (
            ":memory:"
            if demo_mode
            else os.environ.get("ROBODATAOPS_DB", str(PROJECT / "var/workbench.duckdb"))
        )
        st.session_state["_store"] = Store(path)
    return st.session_state["_store"]


def target_editor(targets: list[Target], batch) -> list[Target]:
    rows = [
        {
            "task_id": t.task_id,
            "task": batch.tasks.get(t.task_id, t.task_id),
            "target": t.target,
            "cost_yuan": t.cost_cents / 100,
            "capacity": t.capacity,
            "weight": t.weight,
        }
        for t in targets
    ]
    edited = st.data_editor(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        disabled=["task_id", "task"],
        key=f"target-editor-{batch.snapshot_id}",
        column_config={
            "task_id": st.column_config.TextColumn("任务 ID", width="small"),
            "task": st.column_config.TextColumn("任务", width="large"),
            "target": st.column_config.NumberColumn(
                "目标条数", min_value=0, max_value=100000, step=1
            ),
            "cost_yuan": st.column_config.NumberColumn(
                "合格单价 / 元", min_value=0.01, max_value=100000, step=0.5, format="¥ %.2f"
            ),
            "capacity": st.column_config.NumberColumn(
                "合格交付上限", min_value=0, max_value=100000, step=1
            ),
            "weight": st.column_config.NumberColumn(
                "优先权重", min_value=0.0, max_value=100.0, step=0.5
            ),
        },
    )
    result = []
    for row in edited.to_dict("records"):
        for field in ("target", "capacity"):
            value = row[field]
            if pd.isna(value) or isinstance(value, bool) or float(value) != int(value):
                raise ValidationError("目标和产能必须为非负整数")
        result.append(
            Target(
                str(row["task_id"]),
                int(row["target"]),
                money_to_cents(row["cost_yuan"]),
                int(row["capacity"]),
                float(row["weight"]),
                "simulated",
            )
        )
    return result


def render_overview(batch, audit, reviews, targets):
    states = episode_states(batch, audit, reviews)
    counts = Counter(row["status"] for row in states)
    columns = st.columns(4)
    for column, label, value, detail in [
        (columns[0], "本次轨迹", len(states), "按完整 episode 计数"),
        (columns[1], "按当前口径计入", counts["accepted"], "表格契约 + 当前复核结论"),
        (columns[2], "待人工复核", counts["pending"], "复核后可能弥补部分缺口"),
        (
            columns[3],
            "阻断 / 证据不足",
            counts["blocked"] + counts["unchecked"],
            f"阻断 {counts['blocked']} · 未完成 {counts['unchecked']}",
        ),
    ]:
        column.metric(label, value)
        column.caption(detail)
    left, right = st.columns([1.8, 1], gap="large")
    frame = coverage(batch, audit, reviews, targets)
    with left:
        st.subheader("任务覆盖与当前缺口")
        st.caption("目标、单价和产能为模拟情景参数，可在补采规划页调整。")
        display_coverage(frame)
    with right:
        st.subheader("各任务验收状态")
        chart = frame.set_index("task_id")[["accepted", "pending", "blocked", "unchecked"]].rename(
            columns={
                "accepted": "计入",
                "pending": "待复核",
                "blocked": "阻断",
                "unchecked": "证据不足",
            }
        )
        st.bar_chart(chart, color=["#087f6d", "#cf994b", "#bd6350", "#b6c2bc"], height=270)
        unknown = sum(row["task_id"] not in batch.tasks for row in states)
        if unknown:
            st.warning(f"另有 {unknown} 条轨迹无法明确归入已知任务，未计入以上任务数量。")
    st.subheader("轨迹清单")
    task_options = ["全部", *sorted({str(row["task_id"]) for row in states})]
    selected_task = st.selectbox("按任务筛选轨迹", task_options)
    rows = [
        row for row in states if selected_task == "全部" or str(row["task_id"]) == selected_task
    ]
    display = pd.DataFrame(rows).rename(
        columns={
            "episode_index": "Episode",
            "task_id": "任务 ID",
            "status": "验收状态",
            "length": "读取帧数",
            "declared_length": "声明帧数",
            "finding_count": "发现数",
        }
    )
    display["验收状态"] = display["验收状态"].map(STATUS_LABELS)
    st.dataframe(
        display[["Episode", "任务 ID", "验收状态", "读取帧数", "声明帧数", "发现数"]],
        hide_index=True,
        width="stretch",
        height=285,
    )


def display_coverage(frame):
    columns = ["task", "received", "accepted", "pending", "target", "deficit", "optimistic_deficit"]
    st.dataframe(
        frame[columns].rename(
            columns={
                "task": "任务",
                "received": "本次收到",
                "accepted": "当前计入",
                "pending": "待复核",
                "target": "目标",
                "deficit": "保守缺口",
                "optimistic_deficit": "乐观缺口",
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_review(batch, audit, reviews, db):
    st.caption("确认问题会在当前验收口径下排除该轨迹。驳回只撤销这一项标记，其他阻断仍然生效。")
    filters = st.columns(2)
    state = filters[0].selectbox("复核状态", ["全部", "未复核", "已确认", "已驳回", "已暂缓"])
    severity = filters[1].selectbox("发现类型", ["全部", "技术阻断", "复核信号"])
    labels = {None: "未复核", "confirmed": "已确认", "dismissed": "已驳回", "deferred": "已暂缓"}
    findings = [
        f
        for f in audit.findings
        if (state == "全部" or labels[reviews.get(f.finding_id, {}).get("decision")] == state)
        and (severity == "全部" or (severity == "技术阻断") == f.automatic_block)
    ]
    if not findings:
        st.success("当前筛选下没有待处理的发现。")
    else:
        findings.sort(key=lambda f: (not f.automatic_block, f.episode_index, f.rule_id))
        left, right = st.columns([1, 1.5], gap="large")
        with left:
            st.subheader(f"复核队列 · {len(findings)} 项")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Episode": f.episode_index,
                            "规则": f.rule_id,
                            "发现": f.title,
                            "状态": labels[reviews.get(f.finding_id, {}).get("decision")],
                        }
                        for f in findings
                    ]
                ),
                hide_index=True,
                width="stretch",
                height=300,
            )
            finding_id = st.selectbox(
                "选择问题",
                [f.finding_id for f in findings],
                format_func=lambda value: next(
                    f"EP {f.episode_index:04d} · {f.rule_id} · {f.title}"
                    for f in findings
                    if f.finding_id == value
                ),
            )
        finding = next(f for f in findings if f.finding_id == finding_id)
        episode = next(ep for ep in batch.episodes if ep.episode_index == finding.episode_index)
        with right:
            st.subheader(f"EP {finding.episode_index:04d} · {finding.title}")
            st.caption(
                f"字段 {finding.field} · 规则 {finding.rule_id} / {audit.profile.version} · 区间为轨迹内行位置"
            )
            a, b = st.columns(2)
            a.markdown("**预期条件**")
            a.json(jsonable(finding.expected), expanded=True)
            b.markdown("**实际观测**")
            b.json(jsonable(finding.observed), expanded=True)
            if finding.frame_start is not None:
                st.caption(
                    f"证据范围：行 {finding.frame_start}–{finding.frame_end}，命中 {finding.hit_count} 处"
                )
            with st.form(f"review-{finding.finding_id}"):
                decision = st.radio(
                    "复核决定", list(DECISIONS), format_func=DECISIONS.get, horizontal=False
                )
                reason = st.text_area("复核理由", placeholder="写明依据、修复建议或需要补充的信息")
                if st.form_submit_button("保存复核决定", type="primary"):
                    try:
                        db.review(finding.finding_id, decision, reason)
                        st.session_state["_flash"] = "复核已保存，覆盖与缺口已按新结论重新计算。"
                        st.rerun()
                    except ValidationError as exc:
                        st.error(str(exc))
        st.subheader("轨迹原始证据")
        if episode.rows:
            start = max(0, (finding.frame_start or 0) - 3)
            end = min(
                len(episode.rows),
                (finding.frame_end if finding.frame_end is not None else start + 6) + 4,
            )
            evidence_rows = [
                {
                    "frame_index": r.get("frame_index"),
                    "timestamp": r.get("timestamp"),
                    "state": str(r.get("observation.state")),
                    "action": str(r.get("action")),
                }
                for r in episode.rows[start:end]
            ]
            st.dataframe(pd.DataFrame(evidence_rows), hide_index=True, width="stretch")
            valid = [
                (r.get("frame_index"), r.get("action"))
                for r in episode.rows
                if isinstance(r.get("action"), list)
                and len(r["action"]) == batch.info["features"]["action"]["shape"][0]
            ]
            if valid:
                chart = pd.DataFrame(
                    [values for _, values in valid], index=[index for index, _ in valid]
                )
                chart.columns = [f"action[{i}]" for i in chart.columns]
                st.line_chart(chart, height=220)
                st.caption(
                    "曲线显示维度可读的原始行，缺值或错误维度请以上方证据为准。视频未下载、未做同步验收。"
                )
        else:
            st.warning(episode.read_error or "没有可读取的轨迹行。")
    with st.expander("查看追加保存的复核历史"):
        history = db.history(audit.run_id)
        if history:
            st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
        else:
            st.caption("当前检查运行尚无人工复核记录。")


def render_planning(batch, audit, reviews, targets, db, target_key):
    if not targets:
        st.warning("尚无可配置目标任务，请先补充任务映射。")
        return
    st.subheader("采集目标与交付约束")
    st.caption("数量单位为验收合格 episode；下列目标、单价、产能和权重均为模拟情景输入。")
    try:
        targets = target_editor(targets, batch)
        frame = coverage(batch, audit, reviews, targets)
        tasks = planning_tasks(frame)
        st.session_state[target_key] = targets
    except (ValidationError, ValueError, TypeError) as exc:
        st.error(str(exc))
        return
    display_coverage(frame)
    unresolved = sum(
        row["status"] in {"pending", "unchecked"} for row in episode_states(batch, audit, reviews)
    )
    if unresolved:
        st.caption(
            f"仍有 {unresolved} 条待复核或证据不足。当前按保守缺口规划；先完成复核可能减少新增采购。"
        )
    a, b = st.columns([1, 2])
    budget = a.number_input(
        "总预算 / 元", min_value=0.0, max_value=1000000.0, value=800.0, step=50.0
    )
    with b:
        st.caption("优化目标：尽量弥补各任务当前缺口的加权比例。允许剩余缺口和预算余款。")
        generate = st.button("生成并保存方案", type="primary", width="stretch")
    context = context_for(batch, audit, reviews, targets)
    budget_cents = money_to_cents(budget)
    input_id = digest({"context": context, "tasks": tasks, "budget": budget_cents})
    if generate:
        try:
            plans = compare_plans(tasks, budget_cents)
            ids = {
                plan.strategy: db.save_plan(plan, tasks, context)
                for plan in plans
                if plan.allocation is not None
                and plan.status in {"optimal", "feasible", "heuristic", "no_gap"}
            }
            st.session_state["_comparison"] = {"input_id": input_id, "plans": plans, "ids": ids}
        except ValidationError as exc:
            st.error(str(exc))
    result = st.session_state.get("_comparison")
    if not result or result["input_id"] != input_id:
        st.info(
            "设置参数后生成方案。复核或目标变化后，旧方案会保留在历史中，需要重新计算当前方案。"
        )
    else:
        st.subheader("同一预算下的方案比较")
        comparison = [
            {
                "方案": STRATEGY_NAMES[p.strategy],
                "状态": PLAN_STATUS[p.status],
                "预计费用 / 元": p.spent_cents / 100,
                "预算余款 / 元": (budget_cents - p.spent_cents) / 100,
                "加权剩余缺口": round(p.residual_loss, 4),
                "求解耗时 / ms": round(p.elapsed_seconds * 1000, 1),
            }
            for p in result["plans"]
        ]
        st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
        strategy = st.radio(
            "查看方案",
            list(STRATEGY_NAMES),
            index=2,
            format_func=STRATEGY_NAMES.get,
            horizontal=True,
        )
        plan = next(p for p in result["plans"] if p.strategy == strategy)
        st.caption(plan.message)
        if plan.allocation is not None:
            columns = st.columns(3)
            columns[0].metric("预计新增合格轨迹", sum(plan.allocation.values()))
            columns[1].metric("预计费用", f"¥ {plan.spent_cents / 100:,.2f}")
            fraction = plan.fulfilled_fraction
            columns[2].metric(
                "本方案弥补当前缺口", f"{fraction:.1%}" if fraction is not None else "无需补采"
            )
            st.caption("该比例只用于当前初始缺口内的方案比较；跨批次请比较固定目标达成率。")
            details = [
                {
                    "任务": t.label,
                    "当前缺口": t.demand,
                    "新增合格数量": plan.allocation[t.task_id],
                    "剩余缺口": t.demand - plan.allocation[t.task_id],
                    "预计费用 / 元": t.cost_cents * plan.allocation[t.task_id] / 100,
                    "交付上限": t.capacity,
                }
                for t in tasks
            ]
            st.dataframe(pd.DataFrame(details), hide_index=True, width="stretch")
            if strategy in result["ids"]:
                payload = db.plan(result["ids"][strategy])
                left, right = st.columns(2)
                left.download_button(
                    "导出补采任务 CSV",
                    plan_csv(payload),
                    file_name=f"collection-{payload['plan_id']}.csv",
                    mime="text/csv",
                    width="stretch",
                )
                right.download_button(
                    "导出带版本的方案 JSON",
                    plan_json(payload),
                    file_name=f"plan-{payload['plan_id']}.json",
                    mime="application/json",
                    width="stretch",
                )
                st.caption(
                    "CSV 包含验收规则与来源版本。执行前请指定交付责任人、周期与实际平台要求。"
                )
        if plan.solver_gap is not None:
            st.caption(f"最优性 gap：{plan.solver_gap:.4g}；目标下界：{plan.solver_bound}")
    with st.expander("已保存方案历史"):
        history = db.list_plans()
        if history:
            selected = st.selectbox("历史方案 ID", [row["plan_id"] for row in history])
            payload = db.plan(selected)
            st.json(
                {"plan_id": selected, "context": payload["context"], "plan": payload["plan"]},
                expanded=False,
            )
            st.download_button(
                "下载历史方案", plan_json(payload), file_name=f"plan-{selected}.json"
            )
            st.markdown("**回流验收**")
            st.caption("仅支持同一来源和相同任务定义。原批次与已经登记的轨迹不会重复计功。")
            st.caption(
                "outstanding 是原方案尚未交付量。更新全部任务覆盖时，请重新导入包含原批次与新增数据的累计快照；本页不自动合并原始文件。"
            )
            relative = st.text_input("到货数据目录（相对项目 data 目录）", value="demo")
            if st.button("按此方案验收到货"):
                try:
                    incoming = load_batch(safe_path(PROJECT / "data", relative))
                    original_profile = RuleProfile(**payload["context"]["profile"])
                    receipt = db.receive(
                        selected, incoming, audit_batch(incoming, original_profile)
                    )
                    st.session_state["_receipt"] = receipt
                except (RoboDataOpsError, OSError, ValueError) as exc:
                    st.error(str(exc))
            receipt = st.session_state.get("_receipt")
            if receipt and receipt["plan_id"] == selected:
                st.dataframe(pd.DataFrame(receipt["items"]), hide_index=True, width="stretch")
                st.caption(
                    f"到货 {receipt['received']} 条；原批次或重复轨迹 {receipt['baseline_or_duplicate']} 条。"
                )
                st.download_button(
                    "导出到货核对结果",
                    canonical_json(receipt),
                    file_name=f"receipt-{receipt['receipt_id']}.json",
                )
        else:
            st.caption("生成方案后，完整版本快照会保存在这里。")


def main():
    with st.sidebar:
        st.markdown(
            '<div class="brand">RoboDataOps<span style="color:#7acdb4"> /</span></div><div class="brand-sub">ROBOT DATA DECISIONS</div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "工作台", ["数据概览", "问题复核", "补采规划"], label_visibility="collapsed"
        )
        st.divider()
        st.caption("当前数据批次")
        sources = {
            "合成故障样例": PROJECT / "data/demo",
            "合成干净对照": PROJECT / "data/derived/clean",
        }
        if (PROJECT / "data/raw/libero/manifest.json").exists():
            sources["LIBERO 公开样本"] = PROJECT / "data/raw/libero"
        elif (PROJECT / "data/public_sample/manifest.json").exists():
            sources["LIBERO 公开样本"] = PROJECT / "data/public_sample"
        sources["本地 v3 数据集"] = None
        source_name = st.selectbox("选择数据", list(sources), label_visibility="collapsed")
        root = sources[source_name]
        if root is None:
            relative = st.text_input("项目 data 目录内的相对路径", value="raw/libero")
            root = safe_path(PROJECT / "data", relative)
        if source_name.startswith("合成") and not (root / "manifest.json").exists():
            generate_demo(root, injected=source_name == "合成故障样例")
        with st.expander("检查设置"):
            signals = st.checkbox("启用短轨迹与低运动复核信号", value=True)
            gap = st.number_input(
                "时间间隔复核倍数", min_value=1.1, max_value=10.0, value=1.8, step=0.1
            )
        reload_data = st.button("重新读取并检查", width="stretch")
        st.divider()
        st.caption("验收口径")
        st.markdown("表格技术契约 + 人工复核")
        st.caption("图像解码、任务成功和策略收益需另行验证。")
        if os.environ.get("ROBODATAOPS_DEMO_MODE") == "1":
            st.caption("演示模式 · 复核与计划仅保留在本会话")
        else:
            st.caption("本地模式 · 复核与方案持久保存")
    profile = RuleProfile(review_signals=signals, max_gap_factor=gap)
    runtime_key = (str(root), profile.profile_id)
    if reload_data or st.session_state.get("_runtime_key") != runtime_key:
        with st.spinner("读取完整轨迹并生成检查证据…"):
            batch = load_batch(root)
            audit = audit_batch(batch, profile)
            store().record_audit(batch, audit)
            st.session_state.update({"_batch": batch, "_audit": audit, "_runtime_key": runtime_key})
    batch, audit, db = st.session_state["_batch"], st.session_state["_audit"], store()
    reviews = db.reviews(audit.run_id)
    target_key = f"targets-{batch.snapshot_id}"
    if target_key not in st.session_state:
        ids = sorted({e.task_id for e in batch.episodes if e.task_id in batch.tasks})
        st.session_state[target_key] = default_targets(ids)
    targets = st.session_state[target_key]
    st.markdown('<div class="eyebrow">WORKSPACE / DEMONSTRATION DATA</div>', unsafe_allow_html=True)
    st.title(
        {
            "数据概览": "从轨迹证据，到采集决策。",
            "问题复核": "每一项判断，都有依据。",
            "补采规划": "把有限预算，分配给明确缺口。",
        }[page]
    )
    st.caption(
        {
            "数据概览": "查看本批次验收状态，识别值得优先处理的任务。",
            "问题复核": "定位原始证据，记录判断与理由，保留完整历史。",
            "补采规划": "调整目标和约束，在相同预算下比较三种方案。",
        }[page]
    )
    public = batch.source_kind == "public"
    pill = {
        "public": "公开仿真示教 · 原始样本",
        "injected": "合成故障注入 · 不代表真实缺陷率",
        "synthetic": "合成干净对照",
        "local": "本地数据 · 来源声明未核验",
    }.get(batch.source_kind, "来源类型未核验")
    st.markdown(
        f'<span class="source-pill {"source-public" if public else ""}">{pill}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="step-strip">01　数据概览　　/　　02　问题复核　　/　　03　补采规划与导出</div>',
        unsafe_allow_html=True,
    )
    if "_flash" in st.session_state:
        st.success(st.session_state.pop("_flash"))
    if page == "数据概览":
        render_overview(batch, audit, reviews, targets)
    elif page == "问题复核":
        render_review(batch, audit, reviews, db)
    else:
        render_planning(batch, audit, reviews, targets, db, target_key)
    with st.expander("数据来源与统计口径"):
        st.json(
            {
                "repo": batch.repo_id,
                "revision": batch.revision,
                "selected_episodes": len(batch.episodes),
                "source_declared_episodes": batch.info.get("total_episodes"),
                "snapshot": batch.snapshot_id,
                "rule_profile": jsonable(profile),
                "run_id": audit.run_id,
                "acceptance": "必需检查完成，且无仍生效阻断或未决发现；每条轨迹只计一次",
                "notice": "技术验收与数量覆盖不代表策略表现；所有业务参数为模拟情景。",
            },
            expanded=False,
        )


try:
    main()
except (RoboDataOpsError, OSError, ValueError) as error:
    st.error(str(error))
    st.info("请检查所选目录是否包含 v3 元数据与表格文件，或切换到合成样例。")
