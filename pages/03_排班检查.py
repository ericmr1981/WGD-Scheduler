"""
排班检查页
"""

import streamlit as st
from scheduler.validation import validate_coverage, ValidationResult

st.set_page_config(page_title="排班检查", page_icon="✅")

st.title("✅ 排班检查")
st.markdown("自动检查和手动审核排班方案。")

# 自动检查区
st.subheader("🤖 自动检查")

hourly_coverage = [
    2, 2, 3, 3, 2, 2, 3, 3, 3, 2, 2, 2  # 10:00-21:00 预测覆盖
]

results = validate_coverage(hourly_coverage, min_required=2, peak_hours=[12, 13, 17, 18])

col1, col2, col3 = st.columns(3)
summary = results.summary()
with col1:
    st.metric("总检查项", summary["total"])
with col2:
    st.metric("通过", summary["passed"], delta_color="normal")
with col3:
    st.metric("未通过", summary["failed"], delta_color="inverse")

st.markdown("### 检查明细")
for check in results.checks:
    if check["passed"]:
        st.success(f"✅ {check['name']}：{check['detail']}")
    else:
        st.error(f"❌ {check['name']}：{check['detail']}")

# 手动检查区
st.subheader("👤 手动检查清单")

manual_checks = [
    "所有员工都分配到合理的班次？",
    "休息日安排是否公平？",
    "高峰期人力是否充足？",
    "是否有员工连续工作超过 8 小时？",
    "每周轮换是否已考虑？",
]

for i, check in enumerate(manual_checks):
    st.checkbox(check, key=f"manual_{i}")

st.markdown("---")
if st.button("✅ 确认通过", type="primary"):
    st.success("排班方案已通过审核！可以发布了。")
