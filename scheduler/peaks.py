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


def estimate_half_hourly_customers(
    base_daily_customers: int,
    open_hour: int = 10,
    close_hour: int = 22,
    day_name: str = "周三",
    is_holiday: bool = False,
    peak_periods: dict | None = None,
) -> list[dict]:
    """
    估算每30分钟的客流量分布

    Args:
        base_daily_customers: 日均客流量
        open_hour: 开门时间（小时）
        close_hour: 关门时间（小时）
        day_name: 星期几
        is_holiday: 是否为节假日
        peak_periods: 自定义高峰时段，格式如 {"weekday_lunch": "12:00-14:00", ...}

    Returns:
        每30分钟客流列表
    """
    from copy import deepcopy

    pattern = get_day_pattern(day_name, is_holiday)
    # 拷贝一份，避免修改全局 DEFAULT_PATTERNS
    pattern = deepcopy(pattern)
    adjusted_total = int(base_daily_customers * pattern.customer_multiplier)

    # 如果提供了自定义高峰时段，覆盖默认 pattern
    if peak_periods:
        _apply_peak_periods(pattern, peak_periods, day_name)

    # 计算各时段的加权系数
    total_weight = 0.0
    weights: list[tuple[int, int, float]] = []  # (start_hour, end_hour, weight)

    for hour in range(open_hour, close_hour):
        factor = 0.5  # 非高峰基准
        for period in pattern.periods:
            if period.start_hour <= hour < period.end_hour:
                factor = period.multiplier
                break
        weights.append((hour, hour + 1, factor))
        total_weight += factor

    # 按30分钟拆分
    result = []
    slots = (close_hour - open_hour) * 2  # 每半小时一个 slot
    base_per_slot = adjusted_total / total_weight / 2 if total_weight > 0 else 0

    for i in range(slots):
        hour_idx = i // 2
        minutes = (i % 2) * 30
        weight = weights[hour_idx][2] if hour_idx < len(weights) else 0.5
        customers = int(base_per_slot * weight)

        time_label = f"{open_hour + hour_idx:02d}:{minutes:02d}"
        result.append({
            "time": time_label,
            "hour": open_hour + hour_idx + minutes / 60,
            "customers": max(customers, 1),
            "is_peak": weight > 0.8,
        })

    return result


def _apply_peak_periods(
    pattern: DayPattern,
    peak_periods: dict,
    day_name: str,
) -> None:
    """将自定义高峰时段应用到 pattern 中"""
    is_weekend = day_name in {"周六", "周日"}
    if is_weekend:
        lunch = peak_periods.get("weekend_lunch", "11:00-14:00")
        dinner = peak_periods.get("weekend_dinner", "16:00-20:00")
    else:
        lunch = peak_periods.get("weekday_lunch", "12:00-14:00")
        dinner = peak_periods.get("weekday_dinner", "17:00-19:00")

    def _parse_range(s: str):
        parts = s.replace("：", ":").replace("－", "-").replace("—", "-").split("-")
        return int(parts[0].split(":")[0]), int(parts[1].split(":")[0])

    pattern.periods = [
        PeakPeriod(*_parse_range(lunch) + ("中", 1.5)),
        PeakPeriod(*_parse_range(dinner) + ("中", 1.5)),
    ]


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
