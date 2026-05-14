"""
高峰模型：平日/周末/节假日三级峰值
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PeakPeriod:
    """高峰时段"""
    start_hour: int
    end_hour: int
    intensity: str  # 低/中/高/极高
    multiplier: float  # 相对于基准的倍数


@dataclass
class DayPattern:
    """日高峰模式"""
    day_type: str  # weekday / weekend / holiday
    periods: List[PeakPeriod]
    customer_multiplier: float  # 相对于工作日的客流倍数


# 默认高峰模式
DEFAULT_PATTERNS: Dict[str, DayPattern] = {
    "weekday": DayPattern(
        day_type="weekday",
        periods=[
            PeakPeriod(12, 14, "中", 1.5),
            PeakPeriod(17, 19, "中", 1.5),
        ],
        customer_multiplier=1.0,
    ),
    "weekend": DayPattern(
        day_type="weekend",
        periods=[
            PeakPeriod(11, 14, "高", 2.0),
            PeakPeriod(16, 20, "高", 2.0),
        ],
        customer_multiplier=1.5,
    ),
    "holiday": DayPattern(
        day_type="holiday",
        periods=[
            PeakPeriod(10, 14, "极高", 2.5),
            PeakPeriod(15, 21, "极高", 2.5),
        ],
        customer_multiplier=2.0,
    ),
}


def get_day_pattern(day_name: str, is_holiday: bool = False) -> DayPattern:
    """
    根据星期几和是否为节假日，返回对应的高峰模式

    Args:
        day_name: 星期几（周一/周二/.../周日）
        is_holiday: 是否为法定节假日

    Returns:
        DayPattern
    """
    if is_holiday:
        return DEFAULT_PATTERNS["holiday"]

    weekday_names = {"周一", "周二", "周三", "周四", "周五"}
    weekend_names = {"周六", "周日"}

    if day_name in weekend_names:
        return DEFAULT_PATTERNS["weekend"]
    return DEFAULT_PATTERNS["weekday"]


def estimate_hourly_customers(
    base_daily_customers: int,
    day_name: str,
    is_holiday: bool = False,
) -> List[Dict[str, object]]:
    """
    估算每小时的客流量分布

    Args:
        base_daily_customers: 日均客流量基准
        day_name: 星期几
        is_holiday: 是否为节假日

    Returns:
        每小时客流列表 [{"hour": 10, "customers": 15}, ...]
    """
    pattern = get_day_pattern(day_name, is_holiday)
    adjusted_total = int(base_daily_customers * pattern.customer_multiplier)

    # 简化的小时分布模型
    hourly_distribution = []
    for hour in range(10, 22):  # 10:00 - 22:00
        factor = 1.0
        for period in pattern.periods:
            if period.start_hour <= hour < period.end_hour:
                factor = period.multiplier
                break
            elif hour < period.start_hour or hour >= 10:
                # 非高峰时段
                pass

        # 非高峰时段系数
        if factor == 1.0:
            factor = 0.5

        share = (1 + (factor - 1)) / sum_hours(pattern)
        customers = int(adjusted_total * share / len(range(10, 22)))

        hourly_distribution.append({
            "hour": hour,
            "customers": max(customers, 1),
            "is_peak": factor > 1.0,
        })

    return hourly_distribution


def sum_hours(pattern: DayPattern) -> float:
    """计算模式的总加权系数（用于分布计算）"""
    total = 0.0
    non_peak_count = 12  # 10:00-22:00 共 12 小时
    peak_hours = 0
    for p in pattern.periods:
        peak_hours += p.end_hour - p.start_hour
    non_peak_count = 12 - peak_hours
    total = non_peak_count * 0.5 + sum(
        (p.end_hour - p.start_hour) * p.multiplier for p in pattern.periods
    )
    return total if total > 0 else 1
