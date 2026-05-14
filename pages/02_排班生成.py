"""
排班生成页 — 支持从 Supabase 加载门店配置
"""

import streamlit as st
from scheduler.core import calculate_min_staff
from scheduler.shifts import get_shifts, generate_weekly_schedule, get_hourly_coverage
from scheduler.rest_days import recommend_rest_days, validate_coverage
from db.supabase_client import get_stores

st.set_page_config(page_title="排班生成", page_icon="📋")

st.title("📋 排班生成")
st.markdown("输入客流预估，自动生成排班方案。")

# ─── 从 Supabase 加载配置 ────────────────────────────────────────

config = st.session_state.get("store_config", None)
store_id = st.session_state.get("store_id", None)

if not config:
    try:
        stores = get_stores()
        if stores:
            s = stores[0]
            config = {
                "id": s["id"],
                "name": s["name"],
                "employees": s["employee_count"],
                "productivity": s["productivity_per_hour"],
                "peak_customers": s.get("peak_customers_per_hour", 60),
                "service_type": s.get("service_type", "纯堂食"),
            }
            st.session_state["store_config"] = config
            st.session_state["store_id"] = s["id"]
    except Exception:
        pass

if config:
    st.info(f"当前门店：{config['name']} | 员工数：{config['employees']} 人 | 单人产能：{config['productivity']} 单/h")
else:
    st.warning("⚠️ 尚未配置门店信息，请先在「门店配置」页面填写并保存。")

# ─── 参数输入 ─────────────────────────────────────────────────────

with st.expander("📥 本周客流预估", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        base_customers = st.number_input("日均客流量（基准）", min_value=10, value=200)
        default_peak = config["peak_customers"] if config else 60
        peak_input = st.number_input("本周高峰每小时客流量", min_value=1, value=default_peak)
    with col2:
        default_emp = config["employees"] if config else 3
        employees = st.number_input("可用员工数", min_value=1, value=default_emp)
        default_prod = config["productivity"] if config else 18
        productivity = st.number_input("单人产能（单/小时）", min_value=1, value=default_prod)

# ─── 生成排班 ─────────────────────────────────────────────────────

if st.button("🔨 生成排班方案", type="primary"):
    # 计算最低在岗人数
    min_staff = calculate_min_staff(peak_input, productivity)

    st.markdown("---")
    st.subheader("📊 排班分析结果")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("最低同时在岗人数", f"{min_staff} 人")
    with col2:
        st.metric("可用员工总数", f"{employees} 人")
    with col3:
        st.metric("单人产能", f"{productivity} 单/h")

    # 排班结构
    st.markdown("### 🕐 推荐班次结构")
    st.markdown("""
    | 班次 | 时间 | 时长 | 特点 |
    |------|------|------|------|
    | **A 班** | 10:00-18:00 | 8h | 覆盖开店+午高峰 |
    | **B 班** | 12:00-20:00 | 8h | 覆盖午高峰+晚高峰 |
    | **C 班** | 14:00-22:00 | 8h | 覆盖晚高峰+打烊 |
    """)

    # 休息日安排
    st.markdown("### 📅 建议休息日安排")
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    emp_names = [f"员工{i+1}" for i in range(employees)]
    rest = recommend_rest_days(emp_names, 2)

    for emp, days in rest.items():
        st.markdown(f"- **{emp}**：休息 {'、'.join(days)}")

    coverage = validate_coverage(rest, week_days)
    st.markdown("**每天在岗人数检查：**")
    cols = st.columns(7)
    for i, day in enumerate(week_days):
        with cols[i]:
            count = coverage.get(day, 0)
            st.metric(day, f"{count} 人",
                      delta="✅" if count >= 2 else "⚠️")

    # 生成每小时覆盖数据（传给排班检查页）
    shifts = get_shifts()
    rotation = {emp_names[i]: ["A", "B", "C"][i % 3] for i in range(employees)}
    full_schedule = generate_weekly_schedule(emp_names, rest, shifts, rotation, week_days)
    # 取周三（普通工作日）作为每小时覆盖示例
    hourly = get_hourly_coverage(full_schedule, shifts, "周三")

    st.session_state["schedule_result"] = {
        "hourly_coverage": hourly,
        "min_required": min_staff,
        "peak_hours": [12, 13, 17, 18],
        "min_staff": min_staff,
        "employees": employees,
    }

    st.success("✅ 排班生成完成！请前往「排班检查」页面进行验证。")
