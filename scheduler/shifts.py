"""
班次生成：A/B/C 三班 + 轮换机制
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Shift:
    """班次定义，支持 30 分钟颗粒度（如 9.5 = 9:30）"""
    name: str
    start: float          # 开始小时（如 9.0, 10.5）
    end: float            # 结束小时
    duration: float       # 持续小时数
    peak_coverage: bool


# 标准三班制（10:00-22:00 营业场景）
STANDARD_SHIFTS = [
    Shift(name="A", start=10, end=18, duration=8, peak_coverage=True),
    Shift(name="B", start=12, end=20, duration=8, peak_coverage=True),
    Shift(name="C", start=14, end=22, duration=8, peak_coverage=False),
]


def get_shifts(
    a_start: float = 10.0, a_end: float = 18.0,
    b_start: float = 12.0, b_end: float = 20.0,
    c_start: float = 14.0, c_end: float = 22.0,
) -> List[Shift]:
    return [
        Shift(name="A", start=a_start, end=a_end, duration=a_end - a_start, peak_coverage=True),
        Shift(name="B", start=b_start, end=b_end, duration=b_end - b_start, peak_coverage=True),
        Shift(name="C", start=c_start, end=c_end, duration=c_end - c_start, peak_coverage=False),
    ]


def _round_half(v: float) -> float:
    """四舍五入到最近的 0.5（30 分钟）"""
    return round(v * 2) / 2


def calculate_shifts(
    open_hour: float = 10.0,
    close_hour: float = 22.0,
    opening_prep_mins: int = 60,
    closing_tasks_mins: int = 60,
    meal_break_mins: int = 60,
    target_hours: float = 8.0,
) -> List[Shift]:
    """
    根据营运参数自动计算 A/B/C 班次时间（30 分钟颗粒度）。

    公式：
      shift_duration = target_hours + meal_break / 60
      A: 从 (open - prep) 开始，持续 duration
      C: 到 (close + closing_tasks) 结束，持续 duration
      B: A 和 C 正中间

    Returns:
        [Shift_A, Shift_B, Shift_C]
    """
    duration = target_hours + meal_break_mins / 60

    a_start = open_hour - opening_prep_mins / 60
    a_end = a_start + duration

    c_end = close_hour + closing_tasks_mins / 60
    c_start = c_end - duration

    b_start = (a_start + c_start) / 2
    b_end = b_start + duration

    return [
        Shift(name="A", start=_round_half(a_start), end=_round_half(a_end),
              duration=duration, peak_coverage=True),
        Shift(name="B", start=_round_half(b_start), end=_round_half(b_end),
              duration=duration, peak_coverage=True),
        Shift(name="C", start=_round_half(c_start), end=_round_half(c_end),
              duration=duration, peak_coverage=False),
    ]


def rotate_shifts(
    current_rotation: Dict[str, str],
    week_number: int,
) -> Dict[str, str]:
    """
    班次轮换 A→B→C→A

    Args:
        current_rotation: 当前轮换 {"张三": "A", "李四": "B", "王五": "C"}
        week_number: 当前周数（用于计算轮换）

    Returns:
        新的轮换分配
    """
    shift_order = ["A", "B", "C"]
    rotation = week_number % 3

    new_rotation = {}
    for i, employee in enumerate(current_rotation.keys()):
        new_idx = (i + rotation) % 3
        new_rotation[employee] = shift_order[new_idx]

    return new_rotation


def generate_weekly_schedule(
    employees: List[str],
    rest_days: Dict[str, List[str]],  # {"张三": ["周一", "周二"]}
    shifts: List[Shift],
    rotation: Dict[str, str],
    week_days: List[str],
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    生成一周排班表

    Args:
        employees: 员工列表
        rest_days: 每人休息日 {"员工名": ["周一", ...]}
        shifts: 班次列表
        rotation: 班次分配 {"员工名": "A"}
        week_days: 一周的天数列表

    Returns:
        {employee: {day: shift_name or None(休息)}}
    """
    schedule = {}

    for emp in employees:
        emp_schedule = {}
        emp_shift = rotation.get(emp, "A")

        for day in week_days:
            if day in rest_days.get(emp, []):
                emp_schedule[day] = None  # 休息
            else:
                emp_schedule[day] = emp_shift

        schedule[emp] = emp_schedule

    return schedule


def get_half_hourly_coverage(
    schedule: Dict[str, Dict[str, Optional[str]]],
    shifts: List[Shift],
    day: str,
) -> list[dict]:
    """
    计算某天每 30 分钟的在岗人数。

    Returns:
        [{"time": "09:00", "staff": 1}, {"time": "09:30", "staff": 1}, ...]
    """
    if not shifts:
        return []
    cov_start = min(s.start for s in shifts)
    cov_end = max(s.end for s in shifts)
    n_slots = int((cov_end - cov_start) * 2)
    coverage = [0] * n_slots
    shift_map = {s.name: s for s in shifts}

    for emp, days in schedule.items():
        shift_name = days.get(day)
        if shift_name is None:
            continue
        shift = shift_map.get(shift_name)
        if shift is None:
            continue
        for slot in range(int(shift.start * 2), int(shift.end * 2)):
            idx = slot - int(cov_start * 2)
            if 0 <= idx < n_slots:
                coverage[idx] += 1

    result = []
    for i, c in enumerate(coverage):
        total_minutes = int((cov_start * 60) + i * 30)
        h, m = divmod(total_minutes, 60)
        result.append({"time": f"{h:02d}:{m:02d}", "staff": c})
    return result
