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
    min_on_duty: int = 2,
    week_days: List[str] = None,
) -> Dict[str, List[str]]:
    """
    推荐错休方案——确保每天在岗人数不低于底线

    以 3 人店为例：
    - 每人休 2 天 / 3 人共 6 个休息位
    - 排满周中 5 天后，多余的 1 个休息位放在周五
    - 周末尽量全员在岗

    Args:
        employees: 员工列表
        rest_days_per_week: 每人每周休息天数
        rest_priority: 休息日优先级列表
        min_on_duty: 每天最低在岗人数（默认 2）
        week_days: 一周所有天的顺序列表

    Returns:
        {employee: ["周一", "周二"]}
    """
    if rest_priority is None:
        rest_priority = REST_PRIORITY
    if week_days is None:
        week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    n = len(employees)
    total_rest_slots = n * rest_days_per_week
    # 即使人力不足也尽量安排休息，每天至少留 1 人在岗
    max_rest_per_day = max(1, n - min_on_duty) if n > min_on_duty else 1

    # 第1步：确定每天安排几个休息额
    day_quota: Dict[str, int] = {d: 0 for d in week_days}
    remaining = total_rest_slots

    for day in rest_priority:
        if remaining <= 0:
            break
        quota = min(max_rest_per_day, remaining)
        day_quota[day] = quota
        remaining -= quota

    # 如果还有剩余，扩大到全部7天
    if remaining > 0:
        for day in week_days:
            if remaining <= 0:
                break
            if day_quota[day] >= max_rest_per_day:
                continue
            day_quota[day] += 1
            remaining -= 1

    # 第2步：每人轮流从可用额度中取休息日
    from collections import deque
    pool: list[str] = []
    for day, quota in day_quota.items():
        pool.extend([day] * quota)

    schedule: Dict[str, List[str]] = {e: [] for e in employees}
    emp_queue = deque(employees)

    while pool and emp_queue:
        emp = emp_queue[0]
        if len(schedule[emp]) >= rest_days_per_week:
            emp_queue.rotate(-1)
            continue
        day = pool.pop(0)
        schedule[emp].append(day)
        emp_queue.rotate(-1)

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
