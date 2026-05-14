"""
核心模块：产能公式、在岗人数计算
"""

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
