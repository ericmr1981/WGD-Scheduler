"""
排班生成页 — 支持客流分布图（30min颗粒度）+ 每日排班明细表 + 营运参数分析
"""

import streamlit as st
import pandas as pd
from scheduler.core import calculate_min_staff, calculate_staffing_requirements
from scheduler.shifts import calculate_shifts, generate_shift_pool, get_half_hourly_coverage
from scheduler.rest_days import recommend_rest_days, validate_coverage
from scheduler.peaks import estimate_half_hourly_customers
from db.supabase_client import get_stores

try:
    from scheduler.optimizer import optimize_schedule
    _HAVE_OPTIMIZER = True
except ImportError:
    _HAVE_OPTIMIZER = False

st.set_page_config(page_title="排班生成", page_icon="📋")

# 求解器状态（仅排班页显示）
if _HAVE_OPTIMIZER:
    st.caption("⚙️ 求解器: CP-SAT (ortools)")
else:
    st.caption("⚙️ 求解器: 规则算法 (fallback)")

st.title("📋 排班生成")
st.markdown("输入日均客流量，自动生成30分钟颗粒度客流分布图和排班方案。")

# 时间格式化辅助：10.5 → "10:30"
def _fmt(h: float) -> str:
    return f"{int(h):02d}:{int(h % 1 * 60):02d}"

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
                "productivity_a": s.get("productivity_a", 24),
                "productivity_b": s.get("productivity_b", 18),
                "productivity_c": s.get("productivity_c", 12),
                "productivity_other": s.get("productivity_other", 15),
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
        f"| 营业 10:00~22:00"
    )
else:
    st.warning("⚠️ 尚未配置门店信息，请先在「门店配置」页面填写并保存。")

# ─── 参数输入 ─────────────────────────────────────────────────────

with st.expander("📥 本周客流预估", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        base_customers = st.number_input(
            "日均客流量（基准）", min_value=10,
            value=st.session_state.get("sv_base", 200), key="sv_base",
            help="输入后下方自动生成30分钟颗粒度客流分布图"
        )
        default_peak = config["peak_customers"] if config else 60
        peak_input = st.number_input("本周高峰每小时客流量", min_value=1,
                                      value=st.session_state.get("sv_peak", default_peak),
                                      key="sv_peak")
    with col2:
        employees = config["employees"] if config else 3
        productivity = config["productivity"] if config else 18

# ─── 30分钟颗粒度客流分布图（自动生成）──────────────────────────

st.markdown("### 📊 日客流分布图（30分钟颗粒度）")

peak_periods = config.get("peak_periods") if config else None

weekday_dist = estimate_half_hourly_customers(
    base_customers, day_name="周三", peak_periods=peak_periods
)
weekend_dist = estimate_half_hourly_customers(
    base_customers, day_name="周六", peak_periods=peak_periods,
)

from streamlit_echarts import st_echarts

times = [d["time"] for d in weekday_dist]
wd_vals = [d["customers"] for d in weekday_dist]
we_vals = [d["customers"] for d in weekend_dist]

st_echarts(options={
    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
    "legend": {"data": ["平日客流", "周末客流"], "top": 0},
    "grid": {"left": 50, "right": 20, "top": 40, "bottom": 50},
    "xAxis": {
        "type": "category",
        "data": times,
        "axisLabel": {"rotate": 45, "fontSize": 10},
    },
    "yAxis": {"type": "value", "name": "客流量",
              "max": max(max(wd_vals), max(we_vals)) * 1.5},
    "series": [
        {"name": "平日客流", "type": "bar", "data": wd_vals,
         "itemStyle": {"color": "#1f77b4"}},
        {"name": "周末客流", "type": "bar", "data": we_vals,
         "itemStyle": {"color": "#ff7f0e"}},
    ],
}, height="350px")
st.caption("📊 平日（周三）vs 周末（周六）客流对比")

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
    open_hour = 10.0
    close_hour = 22.0
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

    with st.expander("📊 排班方案总览", expanded=True):
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
    with col3:
        st.metric("全员每日可用工时", f'{staffing["total_staff_hours_per_day"]}h',
                  help=f"{employees}人 × {target_hours}h/人")
        st.metric("每日最低需求工时", f'{staffing["needed_hours"]}h',
                  help=f"营业时长({close_hour - open_hour}h) × {effective_min_staff}人")
        delta = "✅" if staffing["staff_sufficient"] else "⚠️"
        st.metric("人力充足", delta,
                  help="可用工时 ≥ 需求工时即为充足")

    st.markdown("---")

    # ─── 生成班次池（动态）───────────────────────────────────────
    if _HAVE_OPTIMIZER:
        shifts = generate_shift_pool(
            open_hour=open_hour, close_hour=close_hour,
            opening_prep_mins=opening_prep, closing_tasks_mins=closing_tasks,
            meal_break_mins=meal_break, target_hours=target_hours,
        )
    else:
        shifts = calculate_shifts(
            open_hour=open_hour, close_hour=close_hour,
            opening_prep_mins=opening_prep, closing_tasks_mins=closing_tasks,
            meal_break_mins=meal_break, target_hours=target_hours,
        )
    shift_map = {s.name: s for s in shifts}
    shift_dur = shifts[0].duration if shifts else 9.0
    st.markdown(f"### 🕐 班次池（{len(shifts)} 个可选班次）")
    slot_preview = ", ".join(f"{_fmt(s.start)}-{_fmt(s.end)}" for s in shifts[:5])
    if len(shifts) > 5:
        slot_preview += f" … +{len(shifts)-5}"
    st.caption(f"营业范围内全部 {shift_dur:.0f}h 连续时段（30min颗粒度）: {slot_preview}")

    # ─── 生成排班表 ───────────────────────────────────────────────

    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    emp_names = [f"员工{i+1}" for i in range(employees)]

    # ── 构建 30 分钟客流需求 ─────────────────────────────────────
    demand_30min: dict[str, dict[str, int]] = {}
    for day in week_days:
        dist = estimate_half_hourly_customers(
            base_customers, day_name=day, peak_periods=peak_periods,
        )
        demand_30min[day] = {d["time"]: d["customers"] for d in dist}

    # ── 使用 CP-SAT 求解器 ───────────────────────────────────────
    if _HAVE_OPTIMIZER:
        result = optimize_schedule(
            emp_names=emp_names,
            week_days=week_days,
            shifts=shifts,
            productivity=productivity,
            demand_30min=demand_30min,
            min_staff=1,
            peak_hourly_customers=peak_input,
            peak_periods=peak_periods,
            time_limit_seconds=10,
        )

        if result["status"] == "INFEASIBLE":
            st.error("⚠️ 求解器无法找到可行排班方案，请检查约束条件是否过于严格。")
            st.stop()
        elif result["status"] == "ERROR":
            st.warning("⚠️ 求解器出错，切换到规则算法。")
            _HAVE_OPTIMIZER = False
        else:
            schedule_by_emp = result["schedule"]
    else:
        schedule_by_emp = None

    if not _HAVE_OPTIMIZER or schedule_by_emp is None:
        rest = recommend_rest_days(
            emp_names, 1, min_on_duty=effective_min_staff, week_days=week_days
        )
        full_schedule: dict[str, dict[str, str | None]] = {}
        for day in week_days:
            on_duty = [e for e in emp_names if day not in rest.get(e, [])]
            emp_shifts: dict[str, str | None] = {}
            for emp in emp_names:
                if day in rest.get(emp, []):
                    emp_shifts[emp] = None
                elif len(on_duty) == 3:
                    emp_shifts[emp] = ["A", "B", "C"][on_duty.index(emp)]
                elif len(on_duty) == 2:
                    emp_shifts[emp] = "A" if on_duty.index(emp) == 0 else "C"
                else:
                    emp_shifts[emp] = "A" if emp == on_duty[0] else None
            full_schedule[day] = emp_shifts

        schedule_by_emp = {}
        for emp in emp_names:
            schedule_by_emp[emp] = {}
            for day in week_days:
                schedule_by_emp[emp][day] = full_schedule[day].get(emp)

    # 从 schedule_by_emp 提取休息日
    rest = {}
    for emp in emp_names:
        rest[emp] = [day for day in week_days if schedule_by_emp[emp][day] is None]

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
                day_col.append(f"{sn}班\n({_fmt(s.start)}-{_fmt(s.end)})" if s else f"{sn}班")
        table_data[day] = day_col

    df_schedule = pd.DataFrame(table_data, index=emp_names)
    st.dataframe(df_schedule, use_container_width=True)

    # ─── 每日班次甘特图 ────────────────────────────────────────
    st.markdown("#### 📅 每日班次甘特图")
    cov_gs = int(min(s.start for s in shifts))
    cov_ge = int(max(s.end for s in shifts))
    cov_range = cov_ge - cov_gs
    _GC = {"A": "#4caf50", "B": "#2196f3", "C": "#ff9800"}
    for day in week_days:
        bars_divs = ""
        for emp in emp_names:
            sn = schedule_by_emp[emp].get(day)
            s_obj = shift_map.get(sn) if sn else None
            if not s_obj:
                bars_divs += '<div style="display:flex;align-items:center;height:24px">'
                bars_divs += f'<span style="width:44px;font-size:11px">{emp}</span>'
                bars_divs += '<div style="flex:1;height:20px;background:#ddd;border-radius:3px;text-align:center;font-size:10px;color:#888;line-height:20px">休息</div></div>'
            else:
                pct = (s_obj.start - cov_gs) / cov_range * 100
                w = (s_obj.end - s_obj.start) / cov_range * 100
                c = _GC.get(sn, "#666")
                bars_divs += '<div style="display:flex;align-items:center;height:24px">'
                bars_divs += f'<span style="width:44px;font-size:11px">{emp}</span>'
                bars_divs += '<div style="flex:1;height:20px;background:#eee;border-radius:3px;position:relative">'
                bars_divs += f'<div style="position:absolute;left:{pct:.0f}%;width:{w:.0f}%;height:100%;background:{c};border-radius:3px;text-align:center;font-size:10px;color:#fff;line-height:20px;font-weight:600">{sn}</div></div></div>'

        tl = _fmt(cov_gs)
        tm = _fmt((cov_gs + cov_ge) / 2)
        tr = _fmt(cov_ge)
        html = f'<div style="margin:6px 0;font-family:sans-serif">'
        html += f'<div style="display:flex;font-size:10px;color:#888;margin:0 0 2px 44px"><span style="flex:1">{tl}</span><span style="flex:1;text-align:center">{tm}</span><span style="flex:1;text-align:right">{tr}</span></div>'
        html += bars_divs
        html += f'<div style="font-size:10px;color:#888;margin-top:2px">A班 #4caf50 | B班 #2196f3 | C班 #ff9800 | {day}</div></div>'
        st.markdown(html, unsafe_allow_html=True)
        st.markdown("---")

    # ─── 产能曲线与参考数值 ──────────────────────────────────────
    st.markdown("### 📊 产能拟合曲线")

    def _day_curve(day_name: str) -> pd.DataFrame:
        slots = sorted(demand_30min.get(day_name, {}).keys())
        shift_covers_local: dict[str, set[str]] = {}
        for s in shifts:
            covered: set[str] = set()
            for t in slots:
                h_str, m_str = t.split(":")
                tv = int(h_str) + int(m_str) / 60
                if s.start <= tv < s.end:
                    covered.add(t)
            shift_covers_local[s.name] = covered

        rows = []
        for t in slots:
            staff = sum(
                1 for emp in emp_names
                if schedule_by_emp[emp].get(day_name)
                and t in shift_covers_local.get(schedule_by_emp[emp][day_name], set())
            )
            demand = demand_30min.get(day_name, {}).get(t, 0)
            prod = int(staff * productivity / 2)  # 产能(h) → 30min
            rows.append({"time": t, "客流需求": demand, "员工产量": prod})
        return pd.DataFrame(rows).set_index("time")

    col_a, col_b = st.columns(2)
    with col_a:
        df_wd = _day_curve("周三")
        if not df_wd.empty:
            pd_wd = int(peak_input / 2)  # 小时峰值 → 30分钟
            opts_wd = {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["客流需求", "员工产量", "小时峰值"], "top": 0},
                "grid": {"left": 40, "right": 10, "top": 30, "bottom": 30},
                "xAxis": {"type": "category", "data": list(df_wd.index), "axisLabel": {"fontSize": 8}},
                "yAxis": {"type": "value", "name": "单/30min", "axisLabel": {"fontSize": 10}},
                "series": [
                    {"name": "客流需求", "type": "line", "data": [int(v) for v in df_wd["客流需求"]],
                     "smooth": True, "symbol": "none", "lineStyle": {"width": 2, "color": "#1f77b4"}},
                    {"name": "员工产量", "type": "line", "data": [int(v) for v in df_wd["员工产量"]],
                     "smooth": True, "symbol": "none", "lineStyle": {"width": 2, "color": "#ff7f0e"}},
                ],
            }
            if pd_wd > 0:
                opts_wd["series"].append(
                    {"name": "小时峰值", "type": "line", "data": [pd_wd] * len(df_wd),
                     "symbol": "none", "lineStyle": {"width": 2, "color": "#e74c3c", "type": "dashed"}})
            st_echarts(options=opts_wd, height="250px", key="cp_wd")
        st.caption("📅 平日（周三）")
    with col_b:
        df_we = _day_curve("周六")
        if not df_we.empty:
            pd_we = int(peak_input / 2)  # 小时峰值 → 30分钟
            opts_we = {
                "tooltip": {"trigger": "axis"},
                "legend": {"data": ["客流需求", "员工产量", "小时峰值"], "top": 0},
                "grid": {"left": 40, "right": 10, "top": 30, "bottom": 30},
                "xAxis": {"type": "category", "data": list(df_we.index), "axisLabel": {"fontSize": 8}},
                "yAxis": {"type": "value", "name": "单/30min", "axisLabel": {"fontSize": 10}},
                "series": [
                    {"name": "客流需求", "type": "line", "data": [int(v) for v in df_we["客流需求"]],
                     "smooth": True, "symbol": "none", "lineStyle": {"width": 2, "color": "#1f77b4"}},
                    {"name": "员工产量", "type": "line", "data": [int(v) for v in df_we["员工产量"]],
                     "smooth": True, "symbol": "none", "lineStyle": {"width": 2, "color": "#ff7f0e"}},
                ],
            }
            if pd_we > 0:
                opts_we["series"].append(
                    {"name": "小时峰值", "type": "line", "data": [pd_we] * len(df_we),
                     "symbol": "none", "lineStyle": {"width": 2, "color": "#e74c3c", "type": "dashed"}})
            st_echarts(options=opts_we, height="250px", key="cp_we")
        st.caption("📅 周末（周六）")

    # 计算参考数值（用周三数据）
    df_ref = _day_curve("周三")
    total_capacity_units = df_ref["员工产量"].sum()
    total_demand_units = df_ref["客流需求"].sum()

    # 参考数值
    st.markdown("### 📈 产能利用率")
    utilization = (total_demand_units / total_capacity_units * 100) if total_capacity_units > 0 else 0
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("员工总产能 (日)", f"{total_capacity_units:.0f} 单",
                  help="在岗人数×单人产能 全天累计")
    with col2:
        st.metric("客流量 (日)", f"{total_demand_units:.0f} 单",
                  help="预估客流全天累计")
    with col3:
        st.metric("产能利用率", f"{utilization:.1f}%",
                  help="客流÷产能，越接近100%说明拟合越好")

    # ─── 覆盖数据（传排班检查页）──────────────────────────────────
    half_hourly = get_half_hourly_coverage(schedule_by_emp, shifts, "周三")
    st.session_state["schedule_result"] = {
        "half_hourly_coverage": half_hourly,
        "min_required": effective_min_staff,
        "peak_hours": [12, 13, 17, 18],
        "min_staff": effective_min_staff,
        "employees": employees,
    }

    st.success("✅ 排班生成完成！请前往「排班检查」页面进行验证。")
