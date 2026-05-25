# Monthly Schedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add monthly schedule generation mode to the existing schedule page, with 208h monthly total hours cap (excluding meal time).

**Architecture:** All changes in `pages/02_排班生成.py`. Extract `_render_schedule()` to module level for reuse across 4 weekly results. Add month/week calculation utility. Add radio + month selector UI. Add monthly flow to the button handler.

**Tech Stack:** Python, Streamlit, `calendar` module, CP-SAT (ortools)

---

### Task 1: Extract `_render_schedule()` to module level

**Files:**
- Modify: `pages/02_排班生成.py` (lines 342-429)

Currently `_render_schedule()` is defined inside the button handler (line 342). Move it to module level so it can be called for each week's results. It needs these parameters passed explicitly (currently captured from closure):
- `emp_names`, `week_days`, `shifts`, `demand_30min`, `productivity`, `peak_input`, `shift_map`

- [ ] **Step 1: Move `_render_schedule` definition before line 239 (the button handler)**

Find `def _render_schedule(sch, sol, label, expanded=True):` at line 342 and move the entire function definition to before line 239 (before the `if st.button(...)` block). Make `shift_map`, `demand_30min`, `productivity`, `peak_input`, `emp_names`, `week_days`, `shifts` explicit parameters instead of closure captures.

```python
def _render_schedule(sch, sol, label, expanded, emp_names, week_days, shifts, demand_30min, productivity, peak_input, shift_map):
    st.markdown(f"**{label}**")
    if sol: st.caption(f"得分: {sol.get('objective','?')} | 缺口: {sol.get('gap_total','?')} | 班次种类: {sol.get('shift_types_used','?')}")
    rest_local = {emp: [d for d in week_days if sch[emp].get(d) is None] for emp in emp_names}
    st.markdown("### 休息日安排（每人每周1天）")
    for emp, days in rest_local.items(): st.markdown(f"- **{emp}**：休息 {'、'.join(days)}")
    ci = False
    for emp in emp_names:
        for d in rest_local.get(emp, []):
            i = week_days.index(d)
            if (i>0 and week_days[i-1] in rest_local.get(emp,[])) or (i<len(week_days)-1 and week_days[i+1] in rest_local.get(emp,[])):
                st.warning(f"连续休息 {emp}"); ci = True
    if not ci: st.caption("无连续休息")
    st.markdown("### 员工周工时统计")
    eh = []
    for emp in emp_names:
        th = sum(s.end-s.start for d in week_days for sn in [sch[emp].get(d)] if sn for s in [shift_map.get(sn)] if s)
        eh.append({"员工":emp, "周工时(h)":round(th,1), "上限":54, "状态":"OK" if th<=54 else "NG"})
    st.dataframe(pd.DataFrame(eh).set_index("员工"), use_container_width=True)
    st.markdown("### 每日排班明细表")
    td = {}
    for day in week_days:
        td[day] = []
        for emp in emp_names:
            sn = sch[emp].get(day); s = shift_map.get(sn) if sn else None
            td[day].append(f"{sn}班({_fmt(s.start)}-{_fmt(s.end)})" if s else "休息")
    st.dataframe(pd.DataFrame(td, index=emp_names), use_container_width=True)
    cov_gs = int(min(s.start for s in shifts)); cov_ge = int(max(s.end for s in shifts)); cov_r = cov_ge - cov_gs
    st.markdown("#### 📅 每日班次甘特图")
    _gc = {"A":"#4caf50","B":"#2196f3","C":"#ff9800"}
    for day in week_days:
        time_labels = ""
        for h in range(cov_gs, cov_ge + 1):
            p = (h - cov_gs) / cov_r * 100
            time_labels += f'<span style="position:absolute;left:{p:.0f}%;font-size:8px;color:#888">{h}:00</span>'
        bars = ""
        for emp in emp_names:
            sn = sch[emp].get(day); so = shift_map.get(sn) if sn else None
            if not so:
                bars += f'<div style=display:flex;height:18px><span style=width:30px;font-size:9px>{emp}</span><div style=flex:1;height:14px;background:#eee;border-radius:2px;text-align:center;font-size:8px;color:#999;line-height:14px>休息</div></div>'
            else:
                p = (so.start-cov_gs)/cov_r*100; w = (so.end-so.start)/cov_r*100; c = _gc.get(sn,"#666")
                bars += f'<div style=display:flex;height:18px><span style=width:30px;font-size:9px>{emp}</span><div style=flex:1;height:14px;background:#f0f0f0;border-radius:2px;position:relative><div style=position:absolute;left:{p:.0f}%;width:{w:.0f}%;height:100%;background:{c};border-radius:2px;text-align:center;font-size:8px;color:#fff;line-height:14px>{sn}</div></div></div>'
        st.markdown(f'<div style=font-size:9px;color:#888>{day}</div><div style=position:relative;height:14px;margin:0 0 2px 30px;font-size:0>{time_labels}</div><div>{bars}</div>', unsafe_allow_html=True)
    st.caption("A:green B:blue C:orange")
    st.markdown("### 产能拟合曲线")
    def _dc(dn):
        slots = sorted(demand_30min.get(dn,{}).keys())
        sc = {s.name:{t for t in slots if s.start<=int(t.split(":")[0])+int(t.split(":")[1])/60<s.end} for s in shifts}
        rows = []
        for t in slots:
            staff = sum(1 for emp in emp_names if sch[emp].get(dn) and t in sc.get(sch[emp][dn],set()))
            rows.append({"time":t,"需求":demand_30min.get(dn,{}).get(t,0),"产量":int(staff*productivity/2)})
        return pd.DataFrame(rows).set_index("time")
    ca, cb = st.columns(2)
    with ca:
        df = _dc("周三")
        if not df.empty:
            pv = int(peak_input/2)
            o = {"tooltip":{"trigger":"axis"},"legend":{"data":["需求","产量","峰值"],"top":0},"grid":{"left":40,"right":5,"top":25,"bottom":25},"xAxis":{"type":"category","data":list(df.index),"axisLabel":{"fontSize":8}},"yAxis":{"type":"value","axisLabel":{"fontSize":9}},"series":[
                {"name":"需求","type":"line","data":[int(v) for v in df["需求"]],"smooth":True,"symbol":"none","lineStyle":{"width":2,"color":"#1f77b4"}},
                {"name":"产量","type":"line","data":[int(v) for v in df["产量"]],"smooth":True,"symbol":"none","lineStyle":{"width":2,"color":"#ff7f0e"}},
            ]}
            if pv > 0: o["series"].append({"name":"峰值","type":"line","data":[pv]*len(df),"symbol":"none","lineStyle":{"width":2,"color":"#e74c3c","type":"dashed"}})
            st_echarts(options=o, height="180px", key=f"sc_{id(sch)%10000}_a")
        st.caption("平日(周三)")
    with cb:
        df = _dc("周六")
        if not df.empty:
            pv = int(peak_input/2)
            o = {"tooltip":{"trigger":"axis"},"legend":{"data":["需求","产量","峰值"],"top":0},"grid":{"left":40,"right":5,"top":25,"bottom":25},"xAxis":{"type":"category","data":list(df.index),"axisLabel":{"fontSize":8}},"yAxis":{"type":"value","axisLabel":{"fontSize":9}},"series":[
                {"name":"需求","type":"line","data":[int(v) for v in df["需求"]],"smooth":True,"symbol":"none","lineStyle":{"width":2,"color":"#1f77b4"}},
                {"name":"产量","type":"line","data":[int(v) for v in df["产量"]],"smooth":True,"symbol":"none","lineStyle":{"width":2,"color":"#ff7f0e"}},
            ]}
            if pv > 0: o["series"].append({"name":"峰值","type":"line","data":[pv]*len(df),"symbol":"none","lineStyle":{"width":2,"color":"#e74c3c","type":"dashed"}})
            st_echarts(options=o, height="180px", key=f"sc_{id(sch)%10000}_b")
        st.caption("周末(周六)")
    df_r = _dc("周三")
    tc = df_r["产量"].sum() if not df_r.empty else 0
    td = df_r["需求"].sum() if not df_r.empty else 0
    u = (td/tc*100) if tc>0 else 0
    st.markdown("### 产能利用率")
    a,b,c = st.columns(3)
    with a: st.metric("产能(日)",f"{tc:.0f}")
    with b: st.metric("客流(日)",f"{td:.0f}")
    with c: st.metric("利用率",f"{u:.1f}%")
    st.markdown("---")
```

Note: Remove the duplicate `st.markdown("---")` at the end — it's already present at line 429 in the original code.

- [ ] **Step 2: Update call site in button handler**

After extraction, the existing call at line 456:
```python
_render_schedule(schedule_by_emp, results[0] if _ALL_SOLUTIONS else None, "✅ 最优方案", expanded=True)
```
becomes:
```python
_render_schedule(schedule_by_emp, results[0] if _ALL_SOLUTIONS else None, "✅ 最优方案", True, emp_names, week_days, shifts, demand_30min, productivity, peak_input, shift_map)
```

And lines 457-459:
```python
for vi, alt_sol in enumerate(_ALL_SOLUTIONS[1:], start=2):
    with st.expander(f"备选方案 #{vi}（得分: {alt_sol.get('objective', '?')}）", expanded=False):
        _render_schedule(alt_sol["schedule"], alt_sol, f"方案 #{vi}", expanded=False)
```
become:
```python
for vi, alt_sol in enumerate(_ALL_SOLUTIONS[1:], start=2):
    with st.expander(f"备选方案 #{vi}（得分: {alt_sol.get('objective', '?')}）", expanded=False):
        _render_schedule(alt_sol["schedule"], alt_sol, f"方案 #{vi}", False, emp_names, week_days, shifts, demand_30min, productivity, peak_input, shift_map)
```

- [ ] **Step 3: Test in browser** — open http://localhost:8502, go to 排班生成, click "生成排班方案" and verify the weekly schedule renders the same as before (Gantt chart, capacity curves, etc.)

- [ ] **Step 4: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "refactor: extract _render_schedule to module level for reuse"
```

---

### Task 2: Add month-to-weeks helper function

**Files:**
- Modify: `pages/02_排班生成.py` (near the top, after imports and before `_fmt()`)

- [ ] **Step 1: Add `import calendar` at top of file**

```python
+import calendar
```

- [ ] **Step 2: Add `_get_month_weeks()` helper after `_fmt()`**

```python
def _get_month_weeks(year: int, month: int) -> list[tuple[str, str, list[str]]]:
    """Return list of (label, date_range, week_days) for a given month.
    
    Example:
        [("第1周", "5/4(一)-5/10(日)", ["周一","周二",...,"周日"]),
         ("第2周", "5/11(一)-5/17(日)", ["周一","周二",...,"周日"]),
         ...]
    """
    # First day of month and its weekday (0=Mon, 6=Sun)
    first_weekday, num_days = calendar.monthrange(year, month)
    # Find first Monday at or after month start
    first_monday = 1 + ((7 - first_weekday) % 7)
    if first_monday > num_days:
        return []  # Would mean month starts on a Monday past end — shouldn't happen
    
    weeks = []
    current_start = first_monday
    week_index = 1
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    while current_start <= num_days:
        current_end = min(current_start + 6, num_days)
        # Build date range string like "5/4-5/10"
        start_str = f"{month}/{current_start}"
        end_str = f"{month}/{current_end}"
        date_range = f"{month}/{current_start}(一)-{month}/{current_end}(日)"
        
        actual_days = current_end - current_start + 1
        this_week_days = week_days[:actual_days]
        
        weeks.append((f"第{week_index}周", date_range, this_week_days))
        
        current_start += 7
        week_index += 1
    
    return weeks
```

- [ ] **Step 3: Verify logic manually**

Pythonically check: 2026年5月 starts on Thursday (weekday=4), so first Monday is May 4. Last day = May 31 (Sunday). So weeks should be:
- W1: May 4(Mon) - May 10(Sun) → 7 days
- W2: May 11(Mon) - May 17(Sun) → 7 days
- W3: May 18(Mon) - May 24(Sun) → 7 days
- W4: May 25(Mon) - May 31(Sun) → 7 days

- [ ] **Step 4: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "feat: add _get_month_weeks helper for monthly scheduling"
```

---

### Task 3: Add monthly mode UI to schedule page

**Files:**
- Modify: `pages/02_排班生成.py`

Add radio and month selector **after** the traffic chart (line ~234) and **before** the `---` separator (line 235).

- [ ] **Step 1: Add schedule type selector**

Insert at line ~234 (after `st.caption(f"📊 {chart_label}")` and the peak_periods display, before `st.markdown("---")`):

```python
st.markdown("---")
# ─── 排班类型选择 ───────────────────────────────────────────
schedule_mode = st.radio(
    "📅 排班类型",
    options=["weekly", "monthly"],
    format_func=lambda x: {"weekly": "按周排班", "monthly": "按月排班"}[x],
    horizontal=True,
    key="schedule_mode",
)

if schedule_mode == "monthly":
    from datetime import date
    today = date.today()
    month_options = [f"{y}年{m}月" for y in range(today.year, today.year + 2) for m in range(1, 13)]
    default_idx = month_options.index(f"{today.year}年{today.month}月")
    selected_month_str = st.selectbox("选择月份", month_options, index=default_idx, key="month_selector")
    # Parse back to year, month
    selected_year = int(selected_month_str.split("年")[0])
    selected_month = int(selected_month_str.split("年")[1].replace("月", ""))
    month_weeks = _get_month_weeks(selected_year, selected_month)
    st.caption(f"本月共 {len(month_weeks)} 周")
```

- [ ] **Step 2: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "feat: add monthly schedule mode UI"
```

---

### Task 4: Implement monthly schedule generation in button handler

**Files:**
- Modify: `pages/02_排班生成.py` (inside the `if st.button(...)` handler, after schedule generation)

The current weekly flow lives inside `if st.button("🔨 生成排班方案", type="primary"):`. We need to add a branch for monthly mode.

- [ ] **Step 1: Add monthly generation branch**

After the weekly `_render_schedule` calls (after line 459, before `st.success()` on line 460), add:

```python
    # ── 月排班模式 ─────────────────────────────────────────────
    if schedule_mode == "monthly" and month_weeks:
        st.markdown("---")
        st.subheader(f"📅 {selected_month_str} 月排班方案")
        
        # Spinner for generation
        with st.spinner(f"正在生成 {len(month_weeks)} 周排班方案..."):
            all_weekly_results = []
            for wi, (week_label, week_daterange, week_days_local) in enumerate(month_weeks):
                with st.status(f"{week_label} ({week_daterange})...", expanded=False) as status:
                    # Run optimizer for this week
                    local_results = optimize_schedule(
                        emp_names=emp_names,
                        week_days=week_days_local,
                        shifts=shifts,
                        productivity=productivity,
                        demand_30min={d: demand_30min.get(d, {}) for d in week_days_local},
                        min_staff=1,
                        peak_hourly_customers=peak_input,
                        peak_periods=peak_periods,
                        num_solutions=1,
                        time_limit_seconds=10,
                    )
                    if local_results and local_results[0]["status"] not in ("INFEASIBLE", "ERROR"):
                        all_weekly_results.append({
                            "label": week_label,
                            "daterange": week_daterange,
                            "week_days": week_days_local,
                            "result": local_results[0],
                        })
                        status.update(label=f"✅ {week_label} ({week_daterange})", state="complete")
                    else:
                        st.error(f"⚠️ {week_label} 排班失败：约束过严")
                        status.update(label=f"❌ {week_label} 失败", state="error")
        
        if not all_weekly_results:
            st.error("⚠️ 所有周排班均生成失败，请检查约束条件。")
        else:
            # ── 月工时统计 ────────────────────────────────────
            meal_break = config.get("meal_break_mins", 30) if config else 30
            monthly_hours = []
            for emp in emp_names:
                total_hours = 0.0
                for w in all_weekly_results:
                    sch = w["result"]["schedule"]
                    for d in w["week_days"]:
                        sn = sch[emp].get(d)
                        s = shift_map.get(sn) if sn else None
                        if s:
                            total_hours += s.end - s.start
                pure_hours = total_hours - (len(all_weekly_results) * len(week_days) * meal_break / 60)  # subtract meals (approximate)
                # More precise: subtract meal_break per shift
                meal_hours_per_shift = meal_break / 60
                total_meals = sum(
                    1 for w in all_weekly_results
                    for d in w["week_days"]
                    if w["result"]["schedule"][emp].get(d) is not None
                )
                pure_hours = total_hours - total_meals * meal_hours_per_shift
                monthly_hours.append({
                    "员工": emp,
                    "月总工时": round(total_hours, 1),
                    "扣除吃饭": round(pure_hours, 1),
                    "上限(h)": 208,
                    "状态": "OK" if pure_hours <= 208 else "⚠️ NG",
                })
            
            st.markdown("### 员工月工时统计")
            st.dataframe(pd.DataFrame(monthly_hours).set_index("员工"), use_container_width=True)
            
            over_limit = [r["员工"] for r in monthly_hours if r["状态"] != "OK"]
            if over_limit:
                st.warning(f"⚠️ {'、'.join(over_limit)} 月总工时超过 208h 上限，请调整产能参数或增加员工。")
            else:
                st.success("✅ 所有员工月总工时均在 208h 限额内")
            
            st.markdown("---")
            
            # ── 各周详情 ─────────────────────────────────────
            for w in all_weekly_results:
                # Build demand_30min subset for this week
                week_demand = {d: demand_30min.get(d, {}) for d in w["week_days"]}
                with st.expander(f"📋 {w['label']} ({w['daterange']}) | 评分: {w['result'].get('objective', '?')}", expanded=(w == all_weekly_results[0])):
                    # Need local shift_map for this week's shifts
                    _render_schedule(
                        w["result"]["schedule"],
                        w["result"],
                        f"{w['label']} ({w['daterange']})",
                        True,
                        emp_names,
                        w["week_days"],
                        shifts,
                        week_demand,
                        productivity,
                        peak_input,
                        shift_map,
                    )
```

- [ ] **Step 2: Test in browser** — go to 排班生成, select 月排班 + May 2026, click generate, verify:
  - 4 weekly schedules generate without errors
  - Monthly hours table shows up
  - Each week is in its own expander with Gantt chart

- [ ] **Step 3: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "feat: implement monthly schedule generation with 4-week runs"
```

---

### Task 5: Final verification

- [ ] **Step 1: Restart Streamlit app**
```bash
# Kill existing, restart
python3 -m streamlit run app.py
```

- [ ] **Step 2: Full manual test**
  1. Open http://localhost:8502
  2. Navigate to store config — verify data loads from Supabase
  3. Navigate to 排班生成 — verify weekly mode still works
  4. Switch to 月排班, select current month, click generate
  5. Wait for 4 weeks to generate (~40s total)
  6. Verify monthly hours table shows correct 208h check
  7. Expand each week to see Gantt charts

- [ ] **Step 3: Save final state and commit**

```bash
git add .
git commit -m "feat: add monthly schedule generation with 208h cap"
```
