"""
复盘迭代页
"""

import streamlit as st
from scheduler.iteration import (
    WeeklyReview,
    calculate_adjusted_productivity,
    suggest_improvements,
    maturity_level,
)

st.set_page_config(page_title="复盘迭代", page_icon="📈")

st.title("📈 复盘迭代")
st.markdown("每周复盘，持续优化排班参数。")

# 成熟度
maturity = maturity_level([WeeklyReview(
    week_start="2026-05-18",
    actual_customers=200,
    actual_staff_hours=72,
    actual_peak_queue_time=5,
    issues=[],
    adjustments={}
)])
st.info(f"📊 排班成熟度：Level {maturity['level']} — {maturity['label']}")

# 本周复盘
st.subheader("📋 本周复盘")

col1, col2 = st.columns(2)
with col1:
    week = st.text_input("周次", value="2026-W20")
    actual_customers = st.number_input("本周实际客流量", min_value=0, value=1200)
    actual_queue = st.slider("高峰排队时间（分钟）", 0, 30, 5)

with col2:
    base_productivity = st.number_input("当前产能参数", value=18)
    actual_output = st.number_input("实际每小时出单数", value=17)
    issues_text = st.text_area("本周遇到的问题（每行一个）", "")

if st.button("📊 生成复盘", type="primary"):
    new_productivity = calculate_adjusted_productivity(
        base_productivity, actual_output
    )

    st.markdown("---")
    st.subheader("📊 复盘结果")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总客流量", f"{actual_customers} 单")
    with col2:
        st.metric("高峰排队时间", f"{actual_queue} 分钟")
    with col3:
        st.metric("建议调整产能", f"{base_productivity} → {new_productivity}",
                  delta=f"{new_productivity - base_productivity:+.1f}")

    if issues_text:
        issues = [l.strip() for l in issues_text.split("\n") if l.strip()]
        review = WeeklyReview(
            week_start=week,
            actual_customers=actual_customers,
            actual_staff_hours=72,
            actual_peak_queue_time=actual_queue,
            issues=issues,
            adjustments={}
        )
        suggestions = suggest_improvements(review, 2)
        if suggestions:
            st.warning("**改进建议：**")
            for s in suggestions:
                st.markdown(f"- {s}")

    st.success("✅ 复盘完成！产能参数已相应调整。")
