"""
参数迭代：复盘修正产能参数
"""

from typing import Dict, Any, List
from dataclasses import dataclass, asdict


@dataclass
class WeeklyReview:
    """每周复盘数据"""
    week_start: str
    actual_customers: int
    actual_staff_hours: float
    actual_peak_queue_time: int  # 高峰期排队时间（分钟）
    issues: List[str]
    adjustments: Dict[str, Any]


def calculate_adjusted_productivity(
    base_productivity: int,
    actual_hourly_output: float,
) -> float:
    """
    根据实际产出调整产能参数

    Args:
        base_productivity: 基准产能（单/h）
        actual_hourly_output: 实际每小时出单数

    Returns:
        调整后的产能
    """
    if actual_hourly_output <= 0:
        return base_productivity

    # 加权平均：70% 实际 + 30% 基准
    adjusted = 0.7 * actual_hourly_output + 0.3 * base_productivity
    return round(adjusted, 1)


def suggest_improvements(
    review: WeeklyReview,
    min_staff_used: int,
) -> List[str]:
    """
    根据周复盘数据提出改进建议
    """
    suggestions = []

    if review.actual_peak_queue_time > 10:
        suggestions.append(
            f"高峰期排队时间 {review.actual_peak_queue_time} 分钟（建议 < 10 分钟），"
            f"考虑增加高峰在岗人数"
        )

    if review.issues:
        suggestions.extend(review.issues[:3])

    return suggestions


def maturity_level(reviews: List[WeeklyReview]) -> Dict[str, Any]:
    """
    排班成熟度评估
    Level 1-5
    """
    level = 1
    n = len(reviews)

    if n >= 4:
        level = 2
    if n >= 12:
        level = 3
    if n >= 24:
        level = 4
    if n >= 52:
        level = 5

    labels = {
        1: "初始级 — 基于经验排班",
        2: "规范级 — 已有标准化流程",
        3: "数据级 — 基于数据分析排班",
        4: "优化级 — 持续优化排班参数",
        5: "智能级 — 排班自动迭代优化",
    }

    return {
        "level": level,
        "label": labels[level],
        "total_reviews": n,
    }
