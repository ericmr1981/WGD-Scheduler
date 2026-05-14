"""
班次生成：A/B/C 三班 + 轮换机制
"""

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Shift:
    """班次定义"""
    name: str           # A / B / C
    start: int          # 开始小时
    end: int            # 结束小时
    duration: int       # 持续小时数
    peak_coverage: bool  # 是否覆盖高峰


# 标准三班制（10:00-22:00 营业场景）
STANDARD_SHIFTS = [
    Shift(name="A", start=10, end=18, duration=8, peak_coverage=True),
    Shift(name="B", start=12, end=20, duration=8, peak_coverage=True),
    Shift(name="C", start=14, end=22, duration=8, peak_coverage=False),
]


def get_shifts(
    a_start: int = 10, a_end: int = 18,
    b_start: int = 12, b_end: int = 20,
    c_start: int = 14, c_end: int = 22,
) -> List[Shift]:
    """
    返回班次列表，支持自定义各班组时间。

    Args:
        a_start / a_end: A 班起止小时
        b_start / b_end: B 班起止小时
        c_start / c_end: C 班起止小时

    Returns:
        [Shift_A, Shift_B, Shift_C]
    """
    return [
        Shift(name="A", start=a_start, end=a_end, duration=a_end - a_start, peak_coverage=True),
        Shift(name="B", start=b_start, end=b_end, duration=b_end - b_start, peak_coverage=True),
        Shift(name="C", start=c_start, end=c_end, duration=c_end - c_start, peak_coverage=False),
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


def get_hourly_coverage(
    schedule: Dict[str, Dict[str, Optional[str]]],
    shifts: List[Shift],
    day: str,
) -> List[int]:
    """
    计算某天每个小时的在岗人数

    Args:
        schedule: 排班表
        shifts: 班次定义
        day: 星期几

    Returns:
        每小时在岗人数列表 [人数(hour=10), ..., 人数(hour=21)]
    """
    if not shifts:
        return []
    cov_start = min(s.start for s in shifts)
    cov_end = max(s.end for s in shifts)
    cov_hours = cov_end - cov_start
    hourly = [0] * cov_hours
    shift_map = {s.name: s for s in shifts}

    for emp, days in schedule.items():
        shift_name = days.get(day)
        if shift_name is None:
            continue

        shift = shift_map.get(shift_name)
        if shift is None:
            continue

        for h in range(shift.start, shift.end):
            idx = h - cov_start
            if 0 <= idx < cov_hours:
                hourly[idx] += 1

    return hourly
