# Export Schedule to Excel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Excel export for schedule results (daily details, weekly hours, monthly hours).

**Architecture:** Add `_export_to_excel()` module-level function in `pages/02_排班生成.py` using `pd.ExcelWriter` + `BytesIO`. Add `st.download_button` in the button handler after schedule results display.

**Tech Stack:** Python, pandas, openpyxl, Streamlit

---

### Task 1: Install openpyxl and add _export_to_excel() function

**Files:**
- Modify: `pages/02_排班生成.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Ensure openpyxl is installed**

```bash
pip3 install openpyxl
```

- [ ] **Step 2: Add import to top of pages/02_排班生成.py**

```python
+import io
```

- [ ] **Step 3: Add _export_to_excel() function at module level**

Add this function after `_fmt()` and `_get_month_weeks()`:

```python
def _export_to_excel(
    schedule_by_emp: dict,
    week_days: list[str],
    emp_names: list[str],
    shifts: list,
    shift_map: dict,
    all_weekly_results: list,
    schedule_mode: str,
    meal_break: int,
    config: dict | None,
) -> io.BytesIO:
    """Generate Excel file in memory and return BytesIO."""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # ── Sheet 1: 排班明细 ──────────────────────────────────
        rows = []
        if schedule_mode == "monthly" and all_weekly_results:
            for w in all_weekly_results:
                label = w["label"]
                for emp in emp_names:
                    for d in w["week_days"]:
                        sn = w["result"]["schedule"][emp].get(d)
                        s = shift_map.get(sn) if sn else None
                        rows.append({
                            "周次": label,
                            "员工": emp,
                            "日期": d,
                            "班次": sn if sn else "休息",
                            "开始": _fmt(s.start) if s else "",
                            "结束": _fmt(s.end) if s else "",
                        })
        else:
            for emp in emp_names:
                for d in week_days:
                    sn = schedule_by_emp[emp].get(d)
                    s = shift_map.get(sn) if sn else None
                    rows.append({
                        "员工": emp,
                        "日期": d,
                        "班次": sn if sn else "休息",
                        "开始": _fmt(s.start) if s else "",
                        "结束": _fmt(s.end) if s else "",
                    })
        df_detail = pd.DataFrame(rows)
        df_detail.to_excel(writer, sheet_name="排班明细", index=False)
        
        # ── Sheet 2: 周工时统计 ────────────────────────────────
        week_rows = []
        if schedule_mode == "monthly" and all_weekly_results:
            for w in all_weekly_results:
                for emp in emp_names:
                    th = sum(
                        s.end - s.start
                        for d in w["week_days"]
                        for sn in [w["result"]["schedule"][emp].get(d)]
                        if sn
                        for s in [shift_map.get(sn)]
                        if s
                    )
                    week_rows.append({
                        "周次": w["label"],
                        "员工": emp,
                        "周工时(h)": round(th, 1),
                        "上限(h)": 54,
                        "状态": "OK" if th <= 54 else "NG",
                    })
        else:
            for emp in emp_names:
                th = sum(
                    s.end - s.start
                    for d in week_days
                    for sn in [schedule_by_emp[emp].get(d)]
                    if sn
                    for s in [shift_map.get(sn)]
                    if s
                )
                week_rows.append({
                    "员工": emp,
                    "周工时(h)": round(th, 1),
                    "上限(h)": 54,
                    "状态": "OK" if th <= 54 else "NG",
                })
        df_week = pd.DataFrame(week_rows)
        df_week.to_excel(writer, sheet_name="周工时统计", index=False)
        
        # ── Sheet 3: 月工时统计（仅月排班）────────────────────
        if schedule_mode == "monthly" and all_weekly_results:
            meal_hours_per_shift = meal_break / 60
            month_rows = []
            for emp in emp_names:
                total_hours = 0.0
                total_meals = 0
                for w in all_weekly_results:
                    for d in w["week_days"]:
                        sn = w["result"]["schedule"][emp].get(d)
                        s = shift_map.get(sn) if sn else None
                        if s:
                            total_hours += s.end - s.start
                            total_meals += 1
                pure = total_hours - total_meals * meal_hours_per_shift
                month_rows.append({
                    "员工": emp,
                    "月总工时": round(total_hours, 1),
                    "扣除吃饭(h)": round(pure, 1),
                    "上限(h)": 208,
                    "状态": "OK" if pure <= 208 else "NG",
                })
            pd.DataFrame(month_rows).to_excel(writer, sheet_name="月工时统计", index=False)
    
    output.seek(0)
    return output
```

- [ ] **Step 4: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('pages/02_排班生成.py', doraise=True)"
```

- [ ] **Step 5: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "feat: add _export_to_excel function for schedule export"
```

---

### Task 2: Add download button in button handler

**Files:**
- Modify: `pages/02_排班生成.py` (inside the button handler)

Add `st.download_button` after the schedule results display, before `st.success()`.

- [ ] **Step 1: Find insertion point in the button handler**

The end of the button handler currently has:
```python
    # ── 月排班模式 ─────────────────────────────────────────────
    if not _HAVE_OPTIMIZER and schedule_mode == "monthly" and month_weeks:
        st.error("⚠️ 月排班模式需要 CP-SAT 求解器，当前不可用。")
    elif schedule_mode == "monthly" and month_weeks:
        ... (monthly display logic)
    
    st.success("✅ 排班生成完成！请前往「排班检查」页面进行验证。")
```

Insert the download button BEFORE `st.success()`:

```python
    # ── 导出 Excel ──────────────────────────────────────────────
    store_name = config["name"] if config else "门店"
    if schedule_mode == "monthly" and all_weekly_results:
        date_tag = selected_month_str  # e.g. "2026年5月"
        excel_data = _export_to_excel(
            schedule_by_emp, week_days, emp_names, shifts, shift_map,
            all_weekly_results, schedule_mode, meal_break, config,
        )
    else:
        date_tag = f"{week_days[0]}-{week_days[-1]}"
        excel_data = _export_to_excel(
            schedule_by_emp, week_days, emp_names, shifts, shift_map,
            [], schedule_mode, meal_break, config,
        )
    st.download_button(
        label="📥 导出 Excel",
        data=excel_data,
        file_name=f"排班方案_{store_name}_{date_tag}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('pages/02_排班生成.py', doraise=True)"
```

- [ ] **Step 3: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "feat: add download button for schedule Excel export"
```

---

### Task 3: Final verification

- [ ] **Step 1: Restart Streamlit app**

```bash
# Kill existing, restart
python3 -m streamlit run app.py
```

- [ ] **Step 2: Manual test**
  1. Open http://localhost:8501
  2. Go to 排班生成, click "生成排班方案" (weekly mode)
  3. Verify "📥 导出 Excel" button appears
  4. Click it, verify the .xlsx downloads
  5. Open .xlsx and check both sheets ("排班明细", "周工时统计")
  6. Switch to 月排班, generate, export, verify 3 sheets including "月工时统计"

- [ ] **Step 3: Final commit**

```bash
git add . -A
git commit -m "feat: add schedule Excel export functionality"
```
