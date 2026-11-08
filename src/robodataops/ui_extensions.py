"""Workbench extensions; domain calculations stay in testable core modules."""

import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from robodataops.cumulative import accumulate
from robodataops.errors import RoboDataOpsError
from robodataops.ingest import load_batch, safe_path
from robodataops.media import inspect, references
from robodataops.metrics import coverage
from robodataops.models import Target, canonical_json
from robodataops.quality import audit_batch
from robodataops.scenarios import (
    counterfactuals,
    export_scenario,
    import_scenario,
    yield_sensitivity,
)
from robodataops.viewer import viewer_html


def media_panel(batch, preferred_episode=None):
    with st.expander("轨迹视频与动作联动", expanded=False):
        available = []
        for ep in batch.episodes:
            refs = references(batch.info, ep.metadata, batch.manifest, batch.root)
            if any(r.path.exists() for r in refs):
                available.append(ep)
        if not available:
            st.caption("当前批次没有已获取的视频证据。未获取不会被标为源数据丢失。")
            return
        choices = [ep.episode_index for ep in available]
        video_key = f"video-ep-{batch.snapshot_id}"
        preference_key = f"video-preference-{batch.snapshot_id}"
        if (
            preferred_episode in choices
            and st.session_state.get(preference_key) != preferred_episode
        ):
            st.session_state[video_key] = preferred_episode
            st.session_state[preference_key] = preferred_episode
        index = st.selectbox("视频轨迹", choices, key=video_key)
        episode = next(ep for ep in available if ep.episode_index == index)
        refs = references(batch.info, episode.metadata, batch.manifest, batch.root)
        camera = st.selectbox(
            "相机", [r.camera for r in refs], key=f"camera-{batch.snapshot_id}-{index}"
        )
        ref = next(r for r in refs if r.camera == camera)
        st.caption(
            f"来源区间 {ref.source_start:.3f}–{ref.source_end:.3f}s；按 metadata 定位。其他相机或未抽查区间不视为通过。"
        )
        if ref.path.exists():
            if ref.path.stat().st_size <= 5_000_000:
                st.iframe(
                    viewer_html(episode, ref),
                    height=470,
                    alt="轨迹视频与动作状态联动 / trajectory evidence",
                )
            else:
                st.video(str(ref.path), start_time=ref.start, end_time=ref.end)
                st.caption("当前为共享原分片播放；提取5MB以下片段后可使用联动游标。")
        else:
            st.info("该相机尚未获取，不能判断视频质量。")
        if st.button("抽查当前视频片段", key=f"inspect-{batch.snapshot_id}-{index}-{camera}"):
            st.json(inspect(ref))


def cumulative_page(project, batch, audit, reviews, targets, db):
    st.subheader("到货后更新累计覆盖")
    st.caption("使用新派生快照保留父版本；同源轨迹只计一次，内容冲突必须先明确处理。")
    st.info(
        "离线示范：切换 LIBERO 公开样本，输入 public_delivery。该补充池是预先保留的公开数据，不是实际新采。"
    )
    relative = st.text_input("新增批次目录（相对 data）", value="public_delivery")
    if st.button("生成累计分析快照", type="primary"):
        try:
            own = st.session_state.setdefault("_snapshot_paths", [])
            if len(own) >= 5:
                st.error("本会话最多创建5份累计快照，请重用已有结果。")
                return
            incoming = load_batch(safe_path(project / "data", relative))
            incoming_audit = audit_batch(incoming, audit.profile)
            db.record_audit(incoming, incoming_audit)
            output = project / "data/derived/snapshots" / uuid.uuid4().hex
            merged = accumulate([batch, incoming], output)
            merged_audit = audit_batch(merged, audit.profile)
            carried = db.carry_reviews(
                [(batch, audit), (incoming, incoming_audit)], merged, merged_audit
            )
            new_reviews = db.reviews(merged_audit.run_id)
            before, after = (
                coverage(batch, audit, reviews, targets),
                coverage(merged, merged_audit, new_reviews, targets),
            )
            rows = before[["task_id", "task", "accepted", "deficit"]].merge(
                after[["task_id", "accepted", "deficit"]],
                on="task_id",
                suffixes=("_before", "_after"),
            )
            st.session_state["_cumulative_result"] = {
                "root": str(output),
                "snapshot": merged.snapshot_id,
                "rows": rows,
                "carried": carried,
                "parents": merged.manifest["parents"],
            }
            own.append(str(output))
        except (RoboDataOpsError, OSError, ValueError) as exc:
            st.error(str(exc))
    result = st.session_state.get("_cumulative_result")
    if result:
        st.dataframe(result["rows"], hide_index=True, width="stretch")
        st.caption(
            f"累计版本 {result['snapshot']}；继承 {result['carried']} 项内容与规则一致的复核。原始文件和旧计划不变。"
        )
        if st.button("切换到累计快照"):
            st.session_state["_next_source"] = f"累计 · {Path(result['root']).name[:8]}"
            st.session_state["_next_targets"] = targets
            st.rerun()


def scenario_loader(batch, db, target_key):
    with st.expander("保存、载入或导入情景"):
        saved = db.scenarios()
        if saved:
            chosen = st.selectbox(
                "已保存情景",
                [s["scenario_id"] for s in saved],
                format_func=lambda i: next(s["name"] for s in saved if s["scenario_id"] == i),
            )
            if st.button("载入所选情景"):
                value = next(s for s in saved if s["scenario_id"] == chosen)
                apply_scenario(
                    import_scenario(canonical_json(value), set(batch.tasks)), batch, target_key
                )
        uploaded = st.file_uploader("导入情景 JSON（不超过128KB）", type=["json"])
        if uploaded is not None and st.button("应用导入情景"):
            try:
                if uploaded.size > 128_000:
                    raise ValueError("文件超过128KB")
                apply_scenario(
                    import_scenario(uploaded.getvalue().decode("utf-8"), set(batch.tasks)),
                    batch,
                    target_key,
                )
            except (RoboDataOpsError, ValueError, UnicodeError) as exc:
                st.error(str(exc))


def apply_scenario(value, batch, target_key):
    st.session_state[target_key] = [Target(**row) for row in value["targets"]]
    st.session_state["budget-yuan"] = value["budget_cents"] / 100
    st.session_state.pop(f"target-editor-{batch.snapshot_id}", None)
    st.rerun()


def scenario_analysis(targets, tasks, budget_cents, db):
    with st.expander("情景版本、反事实与成品率敏感性"):
        name = st.text_input("情景名称", value="本轮预算方案")
        try:
            payload = export_scenario(name, targets, budget_cents)
            a, b = st.columns(2)
            if a.button("保存当前情景"):
                st.success(f"已保存 {db.save_scenario(payload)}")
            b.download_button(
                "导出情景 JSON", payload, file_name="scenario.json", mime="application/json"
            )
            if st.button("计算反事实解释"):
                st.dataframe(
                    pd.DataFrame(counterfactuals(tasks, budget_cents)),
                    hide_index=True,
                    width="stretch",
                )
            attempts = st.checkbox("把当前单价视为每次尝试成本，查看期望成品率情景")
            if attempts:
                st.caption("这里改变了成本含义；期望产出不构成交付保证。")
                st.dataframe(
                    pd.DataFrame(yield_sensitivity(tasks, budget_cents, costs_are_attempts=True)),
                    hide_index=True,
                    width="stretch",
                )
        except (RoboDataOpsError, ValueError) as exc:
            st.error(str(exc))
