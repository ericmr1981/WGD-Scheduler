"""
核心模块：产能公式、在岗人数计算、工时分析
"""

import math
from typing import Dict, Tuple


def calculate_min_staff(
    peak_hourly_customers: int,
    productivity_per_hour: int,
) -> int:
    """
    计算最低同时在岗人数

    公式: 最低在岗人数 = ceil(高峰每小时客流量 / 单人每小时产能)

    Args:
        peak_hourly_customers: 高峰时段每小时预估客流量
        productivity_per_hour: 单人每小时可服务顾客数（产能基准）

    Returns:
        最低同时在岗人数
    """
    if productivity_per_hour <= 0:
        raise ValueError("单人产能必须大于 0")

    min_staff = -(-peak_hourly_customers // productivity_per_hour)  # ceil division
    return max(1, min_staff)  # 至少 1 人


def calculate_total_hours_needed(
    open_hours: float,
    min_staff_per_shift: int,
    num_shifts: int,
) -> float:
    """
    计算每日所需总人时

    Args:
        open_hours: 营业时长（小时）
        min_staff_per_shift: 每班次最低在岗人数
        num_shifts: 班次数量

    Returns:
        每日所需总人时
    """
    return open_hours * min_staff_per_shift


def calculate_available_hours(
    num_employees: int,
    hours_per_employee: float = 8.0,
) -> float:
    """
    计算每日可用总人时

    Args:
        num_employees: 员工总数
        hours_per_employee: 每人每日工时（默认 8h）

    Returns:
        每日可用总人时
    """
    return num_employees * hours_per_employee


def analyze_gap(
    total_hours_needed: float,
    total_hours_available: float,
) -> Dict[str, object]:
    """
    分析人力缺口

    Returns:
        {
            "gap_hours": 差额,
            "gap_ratio": 缺口比例,
            "status": "充足" | "平衡" | "缺口"
        }
    """
    gap = total_hours_needed - total_hours_available
    ratio = gap / total_hours_needed if total_hours_needed > 0 else 0

    if gap <= 0:
        status = "充足"
    elif ratio < 0.2:
        status = "平衡"
    else:
        status = "缺口"

    return {
        "gap_hours": round(gap, 1),
        "gap_ratio": round(ratio, 2),
        "status": status,
    }


def calculate_staffing_requirements(
    open_hour: float,
    close_hour: float,
    opening_prep_mins: int,
    closing_tasks_mins: int,
    meal_break_mins: int,
    max_meals_per_employee: int,
    target_hours_per_employee: float,
    min_staff_on_duty: int,
    peak_min_staff: int,
    employee_count: int,
    opening_staff_count: int = 1,
) -> dict:
    """
    根据营运参数计算完整的排班需求分析

    Args:
        open_hour: 开店时间
        close_hour: 打烊时间
        opening_prep_mins: 开早准备所需分钟数
        closing_tasks_mins: 打烊收尾所需分钟数
        meal_break_mins: 每餐所需分钟数
        max_meals_per_employee: 每人每天最大就餐次数
        target_hours_per_employee: 每人每天目标工时（不含就餐）
        min_staff_on_duty: 全天最低在岗人数底线
        peak_min_staff: 高峰时段所需人数（由产能公式算出）
        employee_count: 可用员工总数

    Returns:
        dict with keys:
            - effective_min_staff: 实际执行的最低在岗人数
            - meal_break_hours: 每餐折合小时数
            - total_meal_time: 每人每天总就餐时间
            - effective_shift_hours: 含就餐的班次总跨度
            - daily_span_hours: 门店每天总跨度（含开早打烊）
            - total_staff_hours_per_day: 全员每日可用工时总和
            - opening_staff_needed: 开早占用人数
            - closing_staff_needed: 打烊占用人数
            - staff_sufficient: 是否充足
    """
    effective_min_staff = max(peak_min_staff, min_staff_on_duty)
    meal_break_hours = meal_break_mins / 60
    total_meal_time = meal_break_hours * max_meals_per_employee
    effective_shift_hours = target_hours_per_employee + total_meal_time
    daily_span_hours = (close_hour - open_hour) + (opening_prep_mins + closing_tasks_mins) / 60

    total_staff_hours_per_day = employee_count * target_hours_per_employee

    # 开早/打烊占用估算
    opening_staff_needed = opening_staff_count if opening_prep_mins > 0 else 0
    closing_staff_needed = 1 if closing_tasks_mins > 0 else 0

    # 简单判断人力是否充足
    operating_hours = close_hour - open_hour
    needed_hours = operating_hours * effective_min_staff
    staff_sufficient = total_staff_hours_per_day >= needed_hours

    return {
        "effective_min_staff": effective_min_staff,
        "meal_break_hours": meal_break_hours,
        "total_meal_time": total_meal_time,
        "effective_shift_hours": effective_shift_hours,
        "daily_span_hours": daily_span_hours,
        "total_staff_hours_per_day": total_staff_hours_per_day,
        "opening_staff_needed": opening_staff_needed,
        "closing_staff_needed": closing_staff_needed,
        "staff_sufficient": staff_sufficient,
        "needed_hours": round(needed_hours, 1),
    }
