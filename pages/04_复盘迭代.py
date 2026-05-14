"""
复盘迭代页 — 带 Supabase 持久化
"""

import streamlit as st
from scheduler.iteration import (
    WeeklyReview,
    calculate_adjusted_productivity,
    suggest_improvements,
    maturity_level,
)
from db.supabase_client import save_review, get_stores

st.set_page_config(page_title="复盘迭代", page_icon="📈")

st.title("📈 复盘迭代")
st.markdown("每周复盘，持续优化排班参数。数据保存在云端。")

# ─── 成熟度 ──────────────────────────────────────────────────────

# 从 Supabase 获取历史复盘记录
store_id = st.session_state.get("store_id", None)
all_reviews = []

try:
    from db.supabase_client import get_client
    if store_id:
        client = get_client()
        resp = client.table("weekly_reviews").select("*").eq("store_id", store_id).order("created_at", desc=True).execute()
        all_reviews = resp.data or []
except Exception:
    pass

# 构造 WeeklyReview 列表用于成熟度计算
review_objects = []
for r in all_reviews:
    review_objects.append(WeeklyReview(
        week_start=r.get("week_start", ""),
        actual_customers=r.get("actual_customers", 0),
        actual_staff_hours=r.get("actual_staff_hours", 0),
        actual_peak_queue_time=r.get("actual_peak_queue_time", 0),
        issues=[],
        adjustments={},
    ))

maturity = maturity_level(review_objects)
st.info(f"📊 排班成熟度：Level {maturity['level']} — {maturity['label']}（已复盘 {maturity['total_reviews']} 次）")

# ─── 本周复盘 ─────────────────────────────────────────────────────

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

# ─── 生成复盘 ─────────────────────────────────────────────────────

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

    # 改进建议
    issues = [l.strip() for l in issues_text.split("\n") if l.strip()] if issues_text else []
    review = WeeklyReview(
        week_start=week,
        actual_customers=actual_customers,
        actual_staff_hours=72,
        actual_peak_queue_time=actual_queue,
        issues=issues,
        adjustments={
            "adjusted_productivity": new_productivity,
            "previous_productivity": base_productivity,
        },
    )
    suggestions = suggest_improvements(review, 2)
    if suggestions:
        st.warning("**改进建议：**")
        for s in suggestions:
            st.markdown(f"- {s}")

    # 保存到 Supabase
    if store_id:
        try:
            save_review({
                "store_id": store_id,
                "week_start": week,
                "actual_customers": actual_customers,
                "actual_staff_hours": 72,
                "actual_peak_queue_time": actual_queue,
                "adjusted_productivity": new_productivity,
                "issues": issues_text,
            })
            st.success("✅ 复盘记录已保存到云端！")
        except Exception as e:
            st.error(f"❌ 保存失败: {e}")
    else:
        st.warning("⚠️ 未关联门店，复盘记录仅在本次会话中有效。请先在「门店配置」保存门店信息。")

# ─── 历史复盘记录 ────────────────────────────────────────────────

if all_reviews:
    st.subheader("📜 历史复盘记录")
    for r in all_reviews[:5]:
        with st.expander(f"📅 {r.get('week_start', 'unknown')} — 客流 {r.get('actual_customers', 0)}"):
            st.markdown(f"- 排队时间: {r.get('actual_peak_queue_time', 0)} 分钟")
            st.markdown(f"- 调整产能: {r.get('adjusted_productivity', '未调整')}")
            if r.get("issues"):
                st.markdown(f"- 问题: {r['issues']}")
