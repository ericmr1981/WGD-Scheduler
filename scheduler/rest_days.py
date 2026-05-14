"""
休息日安排：高峰日少休逻辑
"""

from typing import Dict, List
from dataclasses import dataclass


# 一周的日类型映射
DAY_TYPES = {
    "周一": "weekday",
    "周二": "weekday",
    "周三": "weekday",
    "周四": "weekday",
    "周五": "weekday",
    "周六": "weekend",
    "周日": "weekend",
}

# 建议休息日优先级（高峰日不排休）
REST_PRIORITY = [
    "周二", "周三", "周四",  # 周中低峰
    "周一", "周五",          # 周中但较忙
    # 周六、周日 — 高峰日不安排休息
]


def recommend_rest_days(
    employees: List[str],
    rest_days_per_week: int = 2,
    rest_priority: List[str] = None,
) -> Dict[str, List[str]]:
    """
    推荐错休方案——确保每天至少 2 人在岗

    以 3 人店为例：
    - 每人休 2 天
    - 3 人错开休息，每天至少 2 人在岗
    - 周末尽量全员在岗

    Args:
        employees: 员工列表
        rest_days_per_week: 每人每周休息天数
        rest_priority: 休息日优先级列表

    Returns:
        {employee: ["周一", "周二"]}
    """
    if rest_priority is None:
        rest_priority = REST_PRIORITY

    n = len(employees)
    schedule: Dict[str, List[str]] = {e: [] for e in employees}

    # 分配休息日，每人错开
    day_offset = 0
    for i, emp in enumerate(employees):
        rest_days = []
        for j in range(rest_days_per_week):
            day_idx = (i + j * (n - 1)) % len(rest_priority)
            rest_days.append(rest_priority[day_idx])
        schedule[emp] = rest_days

    return schedule


def validate_coverage(
    rest_days: Dict[str, List[str]],
    week_days: List[str],
) -> Dict[str, int]:
    """
    验证每天在岗人数

    Returns:
        {day: 在岗人数}
    """
    coverage = {}
    for day in week_days:
        on_duty = 0
        for emp, rests in rest_days.items():
            if day not in rests:
                on_duty += 1
        coverage[day] = on_duty
    return coverage
