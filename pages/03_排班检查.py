"""
排班检查页 — 从排班生成结果获取数据
"""

import streamlit as st
from scheduler.validation import validate_coverage, ValidationResult
from db.supabase_client import get_stores

st.set_page_config(page_title="排班检查", page_icon="✅")

st.title("✅ 排班检查")
st.markdown("自动检查和手动审核排班方案。")

# ─── 获取排班数据 ────────────────────────────────────────────────

schedule_data = st.session_state.get("schedule_result", None)

if schedule_data:
    hourly_coverage = schedule_data.get("hourly_coverage", [])
    min_required = schedule_data.get("min_required", 2)
    peak_hours = schedule_data.get("peak_hours", [12, 13, 17, 18])
    st.info("📋 使用排班生成页的最新数据进行检查")
else:
    # 默认演示数据
    hourly_coverage = [
        2, 2, 3, 3, 2, 2, 3, 3, 3, 2, 2, 2  # 10:00-21:00
    ]
    min_required = 2
    peak_hours = [12, 13, 17, 18]
    st.info("ℹ️ 使用演示数据检查。先到「排班生成」页生成排班，这里会同步更新。")

# ─── 自动检查区 ──────────────────────────────────────────────────

st.subheader("🤖 自动检查")

results = validate_coverage(hourly_coverage, min_required, peak_hours)

col1, col2, col3 = st.columns(3)
summary = results.summary()
with col1:
    st.metric("总检查项", summary["total"])
with col2:
    st.metric("通过", summary["passed"], delta_color="normal")
with col3:
    st.metric("未通过", summary["failed"],
              delta=f"-{summary['failed']}" if summary["failed"] > 0 else "0",
              delta_color="inverse")

st.markdown("### 检查明细")
for check in results.checks:
    if check["passed"]:
        st.success(f"✅ {check['name']}：{check['detail']}")
    else:
        st.error(f"❌ {check['name']}：{check['detail']}")

# ─── 手动检查区 ──────────────────────────────────────────────────

st.subheader("👤 手动检查清单")

manual_checks = [
    "所有员工都分配到合理的班次？",
    "休息日安排是否公平？",
    "高峰期人力是否充足？",
    "是否有员工连续工作超过 8 小时？",
    "每周轮换是否已考虑？",
    "开店/打烊 SOP 人手是否安排？",
]

all_checked = True
for i, check in enumerate(manual_checks):
    checked = st.checkbox(check, key=f"manual_{i}")
    if not checked:
        all_checked = False

st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    if st.button("✅ 确认通过", type="primary"):
        st.success("🎉 排班方案已通过审核！可以发布了。")
        st.balloons()

with col2:
    if st.button("📤 发布排班", type="secondary"):
        if all_checked:
            st.success("📋 排班方案已发布！员工可在排班表中查看。")
        else:
            st.warning("⚠️ 还有未确认的手动检查项，建议全部勾选后再发布。")
