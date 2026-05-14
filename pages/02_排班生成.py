"""
排班生成页 — 支持客流分布图（30min颗粒度）+ 每日排班明细表 + 营运参数分析
"""

import streamlit as st
import pandas as pd
from scheduler.core import calculate_min_staff, calculate_staffing_requirements
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
                "opening_prep_mins": s.get("opening_prep_mins", 60),
                "closing_tasks_mins": s.get("closing_tasks_mins", 60),
                "meal_break_mins": s.get("meal_break_mins", 30),
                "max_meals_per_employee": s.get("max_meals_per_employee", 1),
                "target_hours_per_employee": float(s.get("target_hours_per_employee", 8.0)),
                "min_staff_on_duty": s.get("min_staff_on_duty", 1),
                "shift_a_start": s.get("shift_a_start", 10),
                "shift_a_end": s.get("shift_a_end", 18),
                "shift_b_start": s.get("shift_b_start", 12),
                "shift_b_end": s.get("shift_b_end", 20),
                "shift_c_start": s.get("shift_c_start", 14),
                "shift_c_end": s.get("shift_c_end", 22),
            }
            st.session_state["store_config"] = config
            st.session_state["store_id"] = s["id"]
    except Exception:
        pass

if config:
    st.info(
        f"🏪 **{config['name']}** "
        f"| 员工 {config['employees']} 人 "
        f"| 产能 {config['productivity']} 单/h "
        f"| 营业 {config.get('peak_periods',{}).get('weekday_lunch','12:00-14:00').split('-')[0]}:00~{config.get('peak_periods',{}).get('weekend_dinner','16:00-20:00').split('-')[1]}:00"
    )
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

    # 读取营运参数（从 config 或默认值）
    open_hour = 10
    close_hour = 22
    opening_prep = config.get("opening_prep_mins", 60) if config else 60
    closing_tasks = config.get("closing_tasks_mins", 60) if config else 60
    meal_break = config.get("meal_break_mins", 30) if config else 30
    max_meals = config.get("max_meals_per_employee", 1) if config else 1
    target_hours = config.get("target_hours_per_employee", 8.0) if config else 8.0
    min_on_duty = config.get("min_staff_on_duty", 1) if config else 1

    staffing = calculate_staffing_requirements(
        open_hour=open_hour,
        close_hour=close_hour,
        opening_prep_mins=opening_prep,
        closing_tasks_mins=closing_tasks,
        meal_break_mins=meal_break,
        max_meals_per_employee=max_meals,
        target_hours_per_employee=target_hours,
        min_staff_on_duty=min_on_duty,
        peak_min_staff=min_staff,
        employee_count=employees,
    )

    effective_min_staff = staffing["effective_min_staff"]

    # 检测人力缺口
    staff_shortage = effective_min_staff > employees

    if staff_shortage:
        st.error(f"⚠️ **人力不足！** 高峰需要 {effective_min_staff} 人，但只有 {employees} 人可用。缺 {effective_min_staff - employees} 人。建议：降低高峰客流预估、提高单人产能参数，或增加员工。")

    st.markdown("---")
    st.subheader("📊 排班分析结果")

    # ─── 核心指标 ──────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("高峰需求人数", f"{min_staff} 人",
                  help="由产能公式算出：⌈高峰客流÷单人产能⌉")
    with col2:
        st.metric("最低在岗底线", f"{min_on_duty} 人",
                  help="门店配置中设定的安全底线")
    with col3:
        st.metric("实际执行最低人数", f"{effective_min_staff} 人",
                  help="取「高峰需求」和「最低在岗底线」的较大值")
    with col4:
        st.metric("可用员工数", f"{employees} 人")

    # ─── 工时分析 ──────────────────────────────────────────────────
    st.markdown("### ⏱ 工时分析")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("每班目标工时", f"{target_hours}h",
                  help="不含就餐时间的纯工时")
        st.metric("每餐时间", f"{meal_break}min",
                  help="就餐时间不计入工时")
        st.metric("班次总跨度", f'{staffing["effective_shift_hours"]}h',
                  help=f"目标工时+就餐时间，即员工到店总时长")
    with col2:
        st.metric("门店每日总跨度", f'{staffing["daily_span_hours"]}h',
                  help=f"营业时长+开早{opening_prep}min+打烊{closing_tasks}min")
        st.metric("开早占用", f'{staffing["opening_staff_needed"]} 人',
                  help=f"开早需{opening_prep}分钟，至少1人提前到店")
        st.metric("打烊占用", f'{staffing["closing_staff_needed"]} 人',
                  help=f"打烊需{closing_tasks}分钟，至少1人延后离店")
    with col3:
        st.metric("全员每日可用工时", f'{staffing["total_staff_hours_per_day"]}h',
                  help=f"{employees}人 × {target_hours}h/人")
        st.metric("每日最低需求工时", f'{staffing["needed_hours"]}h',
                  help=f"营业时长({close_hour - open_hour}h) × {effective_min_staff}人")
        delta = "✅" if staffing["staff_sufficient"] else "⚠️"
        st.metric("人力充足", delta,
                  help="可用工时 ≥ 需求工时即为充足")

    st.markdown("---")

    # ─── 班次结构说明（含开早/打烊/就餐）───────────────────────────
    a_s, a_e = config.get("shift_a_start", 10), config.get("shift_a_end", 18)
    b_s, b_e = config.get("shift_b_start", 12), config.get("shift_b_end", 20)
    c_s, c_e = config.get("shift_c_start", 14), config.get("shift_c_end", 22)
    st.markdown("### 🕐 班次结构（含开早/打烊/就餐）")
    prep_h = opening_prep / 60
    close_h = closing_tasks / 60
    st.markdown(f"""
    | 时段 | 时间 | 说明 |
    |------|------|------|
    | **开早准备** | {open_hour - prep_h:.0f}:00~{open_hour}:00 | 至少{staffing["opening_staff_needed"]}人提前{opening_prep}分钟到店 |
    | **营业时间** | {open_hour}:00~{close_hour}:00 | 正式营业，共 {close_hour - open_hour}h |
    | **打烊收尾** | {close_hour}:00~{close_hour + close_h:.0f}:00 | 至少{staffing["closing_staff_needed"]}人延后{closing_tasks}分钟离店 |
    | **班次 A** | {a_s}:00~{a_e}:00（含{meal_break}min就餐） | 覆盖开店+午高峰 |
    | **班次 B** | {b_s}:00~{b_e}:00（含{meal_break}min就餐） | 覆盖午高峰+晚高峰 |
    | **班次 C** | {c_s}:00~{c_e}:00（含{meal_break}min就餐） | 覆盖晚高峰+打烊 |
    """)

    # ─── 生成排班表 ───────────────────────────────────────────────

    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    emp_names = [f"员工{i+1}" for i in range(employees)]

    rest = recommend_rest_days(emp_names, 1, min_on_duty=effective_min_staff, week_days=week_days)
    shifts = get_shifts(
        a_start=config.get("shift_a_start", 10), a_end=config.get("shift_a_end", 18),
        b_start=config.get("shift_b_start", 12), b_end=config.get("shift_b_end", 20),
        c_start=config.get("shift_c_start", 14), c_end=config.get("shift_c_end", 22),
    )
    shift_map = {s.name: s for s in shifts}

    # 动态分配：每人每天按当天在岗人数分配班次，确保营业时段全覆盖
    full_schedule: dict[str, dict[str, str | None]] = {}
    for day in week_days:
        on_duty = [e for e in emp_names if day not in rest.get(e, [])]
        emp_shifts: dict[str, str | None] = {}
        for emp in emp_names:
            if day in rest.get(emp, []):
                emp_shifts[emp] = None
            elif len(on_duty) == 3:
                idx = on_duty.index(emp)
                emp_shifts[emp] = ["A", "B", "C"][idx]
            elif len(on_duty) == 2:
                idx = on_duty.index(emp)
                emp_shifts[emp] = "A" if idx == 0 else "C"
            else:
                emp_shifts[emp] = "A" if emp == on_duty[0] else None
        full_schedule[day] = emp_shifts

    # 转置为 {emp: {day: shift}} 格式
    schedule_by_emp: dict[str, dict[str, str | None]] = {}
    for emp in emp_names:
        schedule_by_emp[emp] = {}
        for day in week_days:
            schedule_by_emp[emp][day] = full_schedule[day].get(emp)

    # 休息日说明
    st.markdown("### 📅 休息日安排（每人每周1天）")
    for emp, days in rest.items():
        st.markdown(f"- **{emp}**：休息 {'、'.join(days)}")

    # 验证：连续休息
    consecutive_issue = False
    for emp in emp_names:
        rdays = rest.get(emp, [])
        for d in rdays:
            idx = week_days.index(d)
            if (idx > 0 and week_days[idx - 1] in rdays) or \
               (idx < len(week_days) - 1 and week_days[idx + 1] in rdays):
                st.warning(f"⚠️ {emp} 连续休息 — 违反规则")
                consecutive_issue = True
    if not consecutive_issue:
        st.caption("✅ 无连续休息")

    # 验证：每小时在岗（使用实际班次时间范围）
    cov_start = min(s.start for s in shifts)
    cov_end = max(s.end for s in shifts)
    cov_hours = cov_end - cov_start
    st.markdown(f"### 🔍 每小时在岗验证（{cov_start}:00-{cov_end}:00）")
    all_covered = True
    for day in week_days:
        hourly = [0] * cov_hours
        for emp in emp_names:
            sn = schedule_by_emp[emp][day]
            if sn is None:
                continue
            s = shift_map.get(sn)
            if s:
                for h in range(s.start, s.end):
                    idx = h - cov_start
                    if 0 <= idx < cov_hours:
                        hourly[idx] += 1
        zero = [cov_start + i for i, c in enumerate(hourly) if c == 0]
        mn = min(hourly) if hourly else 0
        if zero:
            st.warning(f"  {day} ⚠️ 最低{mn}人 | 无人时段: {', '.join(f'{h}' for h in zero)}:00")
            all_covered = False
        else:
            st.markdown(f"  {day} ✅ 最低{mn}人")
    if all_covered:
        st.success("✅ 所有营业时段均有员工在岗")

    # ─── 每日排班明细表 ───────────────────────────────────────────
    st.markdown("### 📋 每日排班明细表")

    table_data = {}
    for day in week_days:
        day_col = []
        for emp in emp_names:
            sn = schedule_by_emp[emp][day]
            if sn is None:
                day_col.append("休息")
            else:
                s = shift_map.get(sn)
                day_col.append(f"{sn}班\n({s.start}:00-{s.end}:00)" if s else f"{sn}班")
        table_data[day] = day_col

    df_schedule = pd.DataFrame(table_data, index=emp_names)
    st.dataframe(df_schedule, use_container_width=True)

    # 按班次汇总
    st.markdown("#### 👥 各班次人员分布")
    for day in week_days:
        groups: dict[str, list[str]] = {}
        for emp in emp_names:
            sn = schedule_by_emp[emp][day]
            groups.setdefault(sn if sn else "休息", []).append(emp)

        parts = []
        for k, v in sorted(groups.items()):
            if k == "休息":
                parts.append(f"休息：{'、'.join(v)}")
            else:
                s = shift_map.get(k)
                ts = f"({s.start}:00-{s.end}:00)" if s else ""
                parts.append(f"{k}班{ts}：{'、'.join(v)}")
        st.markdown(f"**{day}** | {' | '.join(parts)}")

    # ─── 每小时覆盖（传排班检查页）────────────────────────────────
    hourly = get_hourly_coverage(schedule_by_emp, shifts, "周三")
    st.session_state["schedule_result"] = {
        "hourly_coverage": hourly,
        "min_required": effective_min_staff,
        "peak_hours": [12, 13, 17, 18],
        "min_staff": effective_min_staff,
        "employees": employees,
    }

    st.success("✅ 排班生成完成！请前往「排班检查」页面进行验证。")
