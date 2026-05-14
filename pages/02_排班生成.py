"""
排班生成页 — 支持客流分布图（30min颗粒度）+ 每日排班明细表
"""

import streamlit as st
import pandas as pd
from scheduler.core import calculate_min_staff
from scheduler.shifts import get_shifts, generate_weekly_schedule, get_hourly_coverage
from scheduler.rest_days import recommend_rest_days, validate_coverage
from scheduler.peaks import estimate_half_hourly_customers
from db.supabase_client import get_stores

st.set_page_config(page_title="排班生成", page_icon="📋")

st.title("📋 排班生成")
st.markdown("输入日均客流量，自动生成30分钟颗粒度客流分布图和排班方案。")

# ─── 从 Supabase / session_state 加载配置 ────────────────────────

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
                "peak_periods": {
                    "weekday_lunch": s.get("weekday_lunch_peak", "12:00-14:00"),
                    "weekday_dinner": s.get("weekday_dinner_peak", "17:00-19:00"),
                    "weekend_lunch": s.get("weekend_lunch_peak", "11:00-14:00"),
                    "weekend_dinner": s.get("weekend_dinner_peak", "16:00-20:00"),
                },
            }
            st.session_state["store_config"] = config
            st.session_state["store_id"] = s["id"]
    except Exception:
        pass

if config:
    st.info(f"🏪 当前门店：{config['name']} | 员工数：{config['employees']} 人 | 单人产能：{config['productivity']} 单/h")
else:
    st.warning("⚠️ 尚未配置门店信息，请先在「门店配置」页面填写并保存。")

# ─── 参数输入 ─────────────────────────────────────────────────────

with st.expander("📥 本周客流预估", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        base_customers = st.number_input(
            "日均客流量（基准）", min_value=10, value=200,
            help="输入后下方自动生成30分钟颗粒度客流分布图"
        )
        default_peak = config["peak_customers"] if config else 60
        peak_input = st.number_input("本周高峰每小时客流量", min_value=1, value=default_peak)
    with col2:
        default_emp = config["employees"] if config else 3
        employees = st.number_input("可用员工数", min_value=1, value=default_emp)
        default_prod = config["productivity"] if config else 18
        productivity = st.number_input("单人产能（单/小时）", min_value=1, value=default_prod)

# ─── 30分钟颗粒度客流分布图（自动生成）──────────────────────────

st.markdown("### 📊 日客流分布图（30分钟颗粒度）")

# 取周三作为平日参考
peak_periods = config.get("peak_periods") if config else None

weekday_dist = estimate_half_hourly_customers(
    base_customers, day_name="周三", peak_periods=peak_periods
)
weekend_dist = estimate_half_hourly_customers(
    base_customers, day_name="周六", peak_periods=peak_periods,
)

df_chart = pd.DataFrame({
    "时间": [d["time"] for d in weekday_dist],
    "平日客流": [d["customers"] for d in weekday_dist],
    "周末客流": [d["customers"] for d in weekend_dist],
})

st.bar_chart(
    df_chart.set_index("时间"),
    height=300,
    use_container_width=True,
)
st.caption("平日以周三为例，周末以周六为例，30分钟颗粒度")

# 显示高峰时段标记
if peak_periods:
    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"**工作日高峰：** {peak_periods.get('weekday_lunch', '12:00-14:00')} | {peak_periods.get('weekday_dinner', '17:00-19:00')}")
    with cols[1]:
        st.markdown(f"**周末高峰：** {peak_periods.get('weekend_lunch', '11:00-14:00')} | {peak_periods.get('weekend_dinner', '16:00-20:00')}")

st.markdown("---")

# ─── 生成排班 ─────────────────────────────────────────────────────

if st.button("🔨 生成排班方案", type="primary"):
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

    # 排班结构说明
    st.markdown("### 🕐 推荐班次结构")
    st.markdown("""
    | 班次 | 时间 | 时长 | 覆盖特点 |
    |------|------|------|----------|
    | **A 班** | 10:00-18:00 | 8h | 开店+午高峰 |
    | **B 班** | 12:00-20:00 | 8h | 午高峰+晚高峰 |
    | **C 班** | 14:00-22:00 | 8h | 晚高峰+打烊 |
    """)

    # ─── 生成排班表 ───────────────────────────────────────────────

    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    emp_names = [f"员工{i+1}" for i in range(employees)]

    rest = recommend_rest_days(emp_names, 2)
    shifts = get_shifts()
    rotation = {emp_names[i]: ["A", "B", "C"][i % 3] for i in range(employees)}
    full_schedule = generate_weekly_schedule(emp_names, rest, shifts, rotation, week_days)

    # 休息日说明
    st.markdown("### 📅 休息日安排")
    for emp, days in rest.items():
        st.markdown(f"- **{emp}**：休息 {'、'.join(days)}")

    coverage = validate_coverage(rest, week_days)
    st.markdown("**每天在岗人数检查：**")
    cols = st.columns(7)
    for i, day in enumerate(week_days):
        with cols[i]:
            count = coverage.get(day, 0)
            st.metric(day, f"{count} 人", delta="✅" if count >= min_staff else "⚠️")

    # ─── 每日排班明细表 ───────────────────────────────────────────
    st.markdown("### 📋 每日排班明细表")

    # 构建排班矩阵：行为员工，列为日期
    table_data = {}
    for day in week_days:
        day_col = []
        for emp in emp_names:
            shift = full_schedule[emp][day]
            if shift is None:
                day_col.append("休息")
            else:
                # 查找班次时间
                shift_obj = next((s for s in shifts if s.name == shift), None)
                if shift_obj:
                    day_col.append(f"{shift} 班 ({shift_obj.start}:00-{shift_obj.end}:00)")
                else:
                    day_col.append(f"{shift} 班")
        table_data[day] = day_col

    df_schedule = pd.DataFrame(table_data, index=emp_names)
    st.dataframe(df_schedule, use_container_width=True)

    # 按班次汇总
    st.markdown("#### 👥 各班次人员分布")
    for day in week_days:
        shift_groups: dict[str, list[str]] = {}
        for emp in emp_names:
            s = full_schedule[emp][day]
            shift_groups.setdefault(s if s else "休息", []).append(emp)

        parts = []
        for shift_name, members in sorted(shift_groups.items()):
            if shift_name == "休息":
                parts.append(f"休息：{'、'.join(members)}")
            else:
                parts.append(f"{shift_name}班：{'、'.join(members)}")

        st.markdown(f"**{day}** | {' | '.join(parts)}")

    # ─── 每小时覆盖（传排班检查页）────────────────────────────────
    hourly = get_hourly_coverage(full_schedule, shifts, "周三")
    st.session_state["schedule_result"] = {
        "hourly_coverage": hourly,
        "min_required": min_staff,
        "peak_hours": [12, 13, 17, 18],
        "min_staff": min_staff,
        "employees": employees,
    }

    st.success("✅ 排班生成完成！请前往「排班检查」页面进行验证。")
