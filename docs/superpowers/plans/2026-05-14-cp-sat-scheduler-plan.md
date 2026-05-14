# CP-SAT 排班求解器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace rule-based shift assignment with Google OR-Tools CP-SAT optimizer that finds optimal schedules under multiple constraints.

**Architecture:** New `scheduler/optimizer.py` module wraps CP-SAT model. The scheduling page calls it instead of rule-based logic, falling back to rules if ortools isn't available.

**Tech Stack:** Google OR-Tools (ortools>=9.11), Python 3.11+

---

### Task 1: Add ortools dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add ortools to requirements.txt**

Append to `/Users/ericmr/Documents/GitHub/WGD-Scheduler-new/requirements.txt`:
```
ortools>=9.11
```

- [ ] **Step 2: Install and verify**

```bash
cd /Users/ericmr/Documents/GitHub/WGD-Scheduler-new
pip install ortools 2>&1 | tail -3
python3 -c "from ortools.sat.python import cp_model; print('OK:', cp_model.CpSolver().SolverVersion())"
```
Expected: `OK: 9.11.x` or similar version number.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add ortools>=9.11 for CP-SAT scheduling"
```

---

### Task 2: Create optimizer module

**Files:**
- Create: `scheduler/optimizer.py`
- Reference: `scheduler/shifts.py` (Shift dataclass)

- [ ] **Step 1: Write the complete optimizer module**

Create `/Users/ericmr/Documents/GitHub/WGD-Scheduler-new/scheduler/optimizer.py`:

```python
"""
CP-SAT 排班求解器

将排班问题建模为约束满足+优化问题，使用 Google OR-Tools 求解。
"""

from __future__ import annotations

from typing import Any

from scheduler.shifts import Shift

# ─── Public API ──────────────────────────────────────────────────


def optimize_schedule(
    emp_names: list[str],
    week_days: list[str],
    shifts: list[Shift],
    productivity: int,
    demand_30min: dict[str, dict[str, int]],
    min_staff: int = 1,
    time_limit_seconds: int = 10,
) -> dict[str, Any]:
    """
    使用 CP-SAT 求解最优排班方案。

    Args:
        emp_names: 员工姓名列表 ["员工1", "员工2", ...]
        week_days: 一周天数 ["周一", "周二", ...]
        shifts: 班次定义列表 [Shift_A, Shift_B, Shift_C]
        productivity: 单人每小时产能
        demand_30min: {day: {time_str: 预估客流}}
        min_staff: 任何时段最低在岗人数
        time_limit_seconds: 求解时间上限

    Returns:
        {
            "status": "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "ERROR",
            "schedule": {emp: {day: shift_name_or_none}},
            "gap_total": int,
            "shift_types_used": int,
            "coverage_report": [{"day": str, "slots": [{"time": str, "staff": int, "gap": int}]}],
        }
    """
    from ortools.sat.python import cp_model

    num_emps = len(emp_names)
    num_days = len(week_days)

    # ── 所有 30 分钟时段（按时间排序） ──────────────────────────
    all_slot_times: list[str] = []
    for day_data in demand_30min.values():
        for t in day_data:
            if t not in all_slot_times:
                all_slot_times.append(t)
    all_slot_times.sort()

    # 每个班次覆盖哪些时段
    shift_covers: dict[str, set[str]] = {}
    for s in shifts:
        covered: set[str] = set()
        for t in all_slot_times:
            h_str, m_str = t.split(":")
            time_val = int(h_str) + int(m_str) / 60
            if s.start <= time_val < s.end:
                covered.add(t)
        shift_covers[s.name] = covered

    # ── 班次名列表（保持顺序） ─────────────────────────────────
    shift_names = [s.name for s in shifts]

    # ── 建模型 ──────────────────────────────────────────────────
    model = cp_model.CpModel()

    # 变量: shift[e][d] ∈ {0, 1, ..., len(shifts)}  (0=休息)
    shift_var: dict[tuple[int, int], cp_model.IntVar] = {}
    for e in range(num_emps):
        for d in range(num_days):
            shift_var[(e, d)] = model.NewIntVar(
                0, len(shifts), f"shift_{e}_{d}"
            )

    # 辅助 BoolVar 通道: is_rest, is_A, is_B, ...
    is_rest: dict[tuple[int, int], cp_model.IntVar] = {}
    is_shift_type: dict[str, dict[tuple[int, int], cp_model.IntVar]] = {
        n: {} for n in shift_names
    }
    for e in range(num_emps):
        for d in range(num_days):
            is_rest[(e, d)] = model.NewBoolVar(f"rest_{e}_{d}")
            for n in shift_names:
                is_shift_type[n][(e, d)] = model.NewBoolVar(f"{n}_{e}_{d}")

            # 每员工每天恰好一个状态
            model.Add(
                is_rest[(e, d)]
                + sum(is_shift_type[n][(e, d)] for n in shift_names)
                == 1
            )

            # 关联整数变量与 BoolVar
            model.Add(shift_var[(e, d)] == 0).OnlyEnforceIf(is_rest[(e, d)])
            for i, n in enumerate(shift_names):
                model.Add(shift_var[(e, d)] == i + 1).OnlyEnforceIf(
                    is_shift_type[n][(e, d)]
                )

    # ── 硬约束 ──────────────────────────────────────────────────

    # 1. 周六日全员到岗（week_days[5]=周六, [6]=周日）
    sat_idx = 5 if len(week_days) > 5 else -1
    sun_idx = 6 if len(week_days) > 6 else -1
    for e in range(num_emps):
        if sat_idx >= 0:
            model.Add(is_rest[(e, sat_idx)] == 0)
        if sun_idx >= 0:
            model.Add(is_rest[(e, sun_idx)] == 0)

    # 2. 无连续休息
    for e in range(num_emps):
        for d in range(num_days - 1):
            model.Add(is_rest[(e, d + 1)] == 0).OnlyEnforceIf(
                is_rest[(e, d)]
            )

    # 3. 任何时段至少 min_staff 人在岗
    for d in range(num_days):
        for t in all_slot_times:
            staff_expr = 0
            for e in range(num_emps):
                for n in shift_names:
                    if t in shift_covers.get(n, set()):
                        staff_expr += is_shift_type[n][(e, d)]
            model.Add(staff_expr >= min_staff)

    # 4. 每人每天 ≤ 9h（18 个半小时时段）
    for e in range(num_emps):
        for d in range(num_days):
            duty_slots = 0
            for n in shift_names:
                duty_slots += (
                    is_shift_type[n][(e, d)] * len(shift_covers.get(n, set()))
                )
            model.Add(duty_slots <= 18)

    # ── 软约束：产能缺口 ────────────────────────────────────────
    gap_vars: list[cp_model.IntVar] = []
    for d in range(num_days):
        day_name = week_days[d]
        slot_list = sorted(demand_30min.get(day_name, {}).keys())
        for t in slot_list:
            demand = demand_30min[day_name][t]
            staff_expr = 0
            for e in range(num_emps):
                for n in shift_names:
                    if t in shift_covers.get(n, set()):
                        staff_expr += is_shift_type[n][(e, d)]
            gap = model.NewIntVar(0, max(demand, 1), f"gap_{d}_{t.replace(':','_')}")
            model.Add(gap >= demand - staff_expr * productivity)
            gap_vars.append(gap)

    total_gap = model.NewIntVar(0, sum(max(v, 1) for v in sum(
        list(demand_30min.get(week_days[d], {}).values())
        for d in range(num_days) if d < len(week_days)
    , [])), "total_gap")
    model.Add(total_gap == sum(gap_vars))

    # ── 软约束：班次种类 ────────────────────────────────────────
    uses_shift: dict[str, cp_model.IntVar] = {}
    for n in shift_names:
        var = model.NewBoolVar(f"uses_{n}")
        all_uses = [
            is_shift_type[n][(e, d)]
            for e in range(num_emps)
            for d in range(num_days)
        ]
        model.AddMaxEquality(var, all_uses)
        uses_shift[n] = var

    shift_type_count = model.NewIntVar(0, len(shift_names), "shift_type_count")
    model.Add(shift_type_count == sum(uses_shift.values()))

    # ── 组合目标 ─────────────────────────────────────────────────
    model.Minimize(1000 * total_gap + shift_type_count)

    # ── 求解 ─────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    status = solver.Solve(model)

    # ── 处理结果 ─────────────────────────────────────────────────
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # 构建排班表
        schedule: dict[str, dict[str, str | None]] = {}
        for e, emp in enumerate(emp_names):
            schedule[emp] = {}
            for d, day in enumerate(week_days):
                val = solver.Value(shift_var[(e, d)])
                if val == 0:
                    schedule[emp][day] = None  # 休息
                else:
                    schedule[emp][day] = shift_names[val - 1]

        # 构建覆盖报告
        coverage_report: list[dict] = []
        for d, day in enumerate(week_days):
            slots_report: list[dict] = []
            for t in all_slot_times:
                demand = demand_30min.get(day, {}).get(t, 0)
                staff_count = sum(
                    1 for e in range(num_emps)
                    for n in shift_names
                    if t in shift_covers.get(n, set())
                    and solver.Value(is_shift_type[n][(e, d)]) == 1
                )
                gap = max(0, demand - staff_count * productivity)
                if demand > 0 or staff_count > 0:
                    slots_report.append({
                        "time": t, "staff": staff_count,
                        "demand": demand, "gap": gap,
                    })
            coverage_report.append({"day": day, "slots": slots_report})

        status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        return {
            "status": status_str,
            "schedule": schedule,
            "gap_total": solver.Value(total_gap),
            "shift_types_used": solver.Value(shift_type_count),
            "coverage_report": coverage_report,
        }
    elif status == cp_model.INFEASIBLE:
        return {"status": "INFEASIBLE", "schedule": {}, "gap_total": -1,
                "shift_types_used": -1, "coverage_report": []}
    else:
        return {"status": "ERROR", "schedule": {}, "gap_total": -1,
                "shift_types_used": -1, "coverage_report": []}
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/ericmr/Documents/GitHub/WGD-Scheduler-new
python3 -c "import py_compile; py_compile.compile('scheduler/optimizer.py', doraise=True); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add scheduler/optimizer.py
git commit -m "feat: add CP-SAT scheduler optimizer"
```

---

### Task 3: Write test for optimizer

**Files:**
- Create: `tests/test_optimizer.py`

- [ ] **Step 1: Write test file**

Create `/Users/ericmr/Documents/GitHub/WGD-Scheduler-new/tests/test_optimizer.py`:

```python
"""Tests for the CP-SAT scheduler optimizer."""

from scheduler.shifts import calculate_shifts
from scheduler.optimizer import optimize_schedule


def test_3_emp_basic_coverage():
    """3 employees, standard params: all hard constraints satisfied."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2", "员工3"]
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    # 生成 30 分钟需求（与排班页逻辑一致）
    demand_30min = {}
    for day in week_days:
        slots = {}
        # 简化的需求模型：高峰 60 单/h，非高峰 20 单/h
        for s in range(9 * 2, 23 * 2):  # 9:00~23:00 每半小时
            h = s // 2
            m = "00" if s % 2 == 0 else "30"
            t = f"{h:02d}:{m}"
            # 午高峰 12-14, 晚高峰 17-19
            if (12 <= h < 14) or (17 <= h < 19):
                slots[t] = 60
            else:
                slots[t] = 20
        demand_30min[day] = slots

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE"), f"Failed: {result['status']}"
    schedule = result["schedule"]

    # 约束 1: 周六日全员在岗
    for emp in emp_names:
        assert schedule[emp]["周六"] is not None, f"{emp} 周六休息"
        assert schedule[emp]["周日"] is not None, f"{emp} 周日休息"

    # 约束 2: 无连续休息
    for emp in emp_names:
        prev_rest = False
        for day in week_days:
            is_rest = schedule[emp][day] is None
            if prev_rest and is_rest:
                assert False, f"{emp} 连续休息"
            prev_rest = is_rest

    # 约束 3: 每人最多 1 天休息
    for emp in emp_names:
        rest_days = sum(1 for d in week_days if schedule[emp][d] is None)
        assert rest_days <= 1, f"{emp} 休息 {rest_days} 天"

    # 覆盖报告验证
    assert len(result["coverage_report"]) == 7
    assert result["gap_total"] >= 0


def test_weekend_full_staff_enforced():
    """Weekend constraint: all employees present Sat and Sun."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2"]
    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    demand_30min = {}
    for day in week_days:
        slots = {}
        for s in range(9 * 2, 23 * 2):
            h = s // 2
            m = "00" if s % 2 == 0 else "30"
            slots[f"{h:02d}:{m}"] = 10
        demand_30min[day] = slots

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    for emp in emp_names:
        assert result["schedule"][emp]["周六"] is not None
        assert result["schedule"][emp]["周日"] is not None


def test_no_consecutive_rest():
    """No consecutive rest constraint."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2", "员工3"]
    week_days = ["周一", "周二", "周三", "周四", "周五"]

    demand_30min = {}
    for day in week_days:
        slots = {}
        for s in range(9 * 2, 23 * 2):
            h = s // 2
            m = "00" if s % 2 == 0 else "30"
            slots[f"{h:02d}:{m}"] = 10
        demand_30min[day] = slots

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    for emp in emp_names:
        prev_rest = False
        for day in week_days:
            is_rest = result["schedule"][emp][day] is None
            assert not (prev_rest and is_rest), f"{emp} consecutive rest"
            prev_rest = is_rest


def test_shift_type_minimization():
    """With 2 employees and low demand, optimizer should use fewer shift types."""
    shifts = calculate_shifts(10, 22, 60, 60, 60, 8.0)
    emp_names = ["员工1", "员工2"]
    week_days = ["周一"]

    demand_30min = {"周一": {}}
    for s in range(9 * 2, 23 * 2):
        h = s // 2
        m = "00" if s % 2 == 0 else "30"
        demand_30min["周一"][f"{h:02d}:{m}"] = 3  # very low demand

    result = optimize_schedule(
        emp_names=emp_names,
        week_days=week_days,
        shifts=shifts,
        productivity=18,
        demand_30min=demand_30min,
        min_staff=1,
        time_limit_seconds=10,
    )

    assert result["status"] in ("OPTIMAL", "FEASIBLE")
    # With very low demand, should use ≤2 shift types
    assert result["shift_types_used"] <= 2
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/ericmr/Documents/GitHub/WGD-Scheduler-new
python3 -m pytest tests/test_optimizer.py -v 2>&1
```
Expected: 4 tests passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_optimizer.py
git commit -m "test: add CP-SAT optimizer tests"
```

---

### Task 4: Integrate optimizer into scheduling page

**Files:**
- Modify: `pages/02_排班生成.py`

- [ ] **Step 1: Add optimizer import and integrate solve flow**

In `/Users/ericmr/Documents/GitHub/WGD-Scheduler-new/pages/02_排班生成.py`:

Add at the top:
```python
try:
    from scheduler.optimizer import optimize_schedule
    _HAVE_OPTIMIZER = True
except ImportError:
    _HAVE_OPTIMIZER = False
```

Then replace the section after `# ─── 生成排班表 ───────────────────────────────────────────────` (around line 221) with:

```python
    # ─── 生成排班表 ───────────────────────────────────────────────

    week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    emp_names = [f"员工{i+1}" for i in range(employees)]

    # ── 构建 30 分钟客流需求 ─────────────────────────────────────
    demand_30min: dict[str, dict[str, int]] = {}
    for day in week_days:
        is_weekend = day in ("周六", "周日")
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
            min_staff=effective_min_staff,
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
        # ── 规则算法 fallback ─────────────────────────────────────
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
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/ericmr/Documents/GitHub/WGD-Scheduler-new
python3 -c "import py_compile; py_compile.compile('pages/02_排班生成.py', doraise=True); print('OK')"
```

- [ ] **Step 3: No import changes needed**

The existing imports (`recommend_rest_days`, `validate_coverage`) are still used in the fallback block, so no import lines need to be removed.

- [ ] **Step 4: Commit**

```bash
git add pages/02_排班生成.py
git commit -m "feat: integrate CP-SAT optimizer into scheduling page with rule fallback"
```

---

### Task 5: Run all existing tests to verify no regressions

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/ericmr/Documents/GitHub/WGD-Scheduler-new
python3 -m pytest tests/ -v 2>&1
```
Expected: All tests pass (including new optimizer tests).

- [ ] **Step 2: Commit final state**

```bash
git add -A
git commit -m "chore: finalize CP-SAT scheduler integration"
git push
```
