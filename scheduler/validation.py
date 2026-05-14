"""
自动检查：产能验证、合规检查
"""

from typing import Dict, List, Any


class ValidationResult:
    """检查结果"""

    def __init__(self):
        self.checks: List[Dict[str, Any]] = []

    def add_check(self, name: str, passed: bool, detail: str):
        self.checks.append({
            "name": name,
            "passed": passed,
            "detail": detail,
        })

    def all_passed(self) -> bool:
        return all(c["passed"] for c in self.checks)

    def summary(self) -> Dict[str, Any]:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c["passed"])
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "all_passed": self.all_passed(),
        }


def validate_coverage(
    hourly_staff: List[int],
    min_required: int,
    peak_hours: List[int],
) -> ValidationResult:
    """
    检查每小时覆盖是否达标

    Args:
        hourly_staff: 每小时在岗人数列表
        min_required: 最低在岗人数要求
        peak_hours: 高峰时段列表 [12, 13, 17, 18, ...]
    """
    result = ValidationResult()

    # 检查最低覆盖
    understaffed = []
    for hour_idx, staff_count in enumerate(hourly_staff):
        if staff_count < min_required:
            understaffed.append((hour_idx + 10, staff_count))

    if understaffed:
        details = "; ".join(f"{h}:00 仅 {c} 人" for h, c in understaffed)
        result.add_check("最低覆盖", False, f"以下时段人力不足：{details}")
    else:
        result.add_check("最低覆盖", True, "所有时段覆盖达标 ✅")

    # 检查高峰覆盖
    peak_understaffed = []
    for hour in peak_hours:
        idx = hour - 10
        if 0 <= idx < len(hourly_staff):
            if hourly_staff[idx] < min_required + 1:
                peak_understaffed.append((hour, hourly_staff[idx]))

    if peak_understaffed:
        details = "; ".join(f"{h}:00 仅 {c} 人" for h, c in peak_understaffed)
        result.add_check("高峰覆盖", False, f"高峰时段人力不足：{details}")
    else:
        result.add_check("高峰覆盖", True, "高峰时段覆盖达标 ✅")

    return result


def validate_cost(
    total_hours: float,
    hourly_rate: float,
    budget: float,
) -> ValidationResult:
    """
    检查人力成本是否在预算内
    """
    result = ValidationResult()
    total_cost = total_hours * hourly_rate

    if total_cost > budget:
        result.add_check(
            "成本预算",
            False,
            f"总成本 ¥{total_cost:.0f} 超出预算 ¥{budget:.0f}，超出 ¥{total_cost - budget:.0f}"
        )
    else:
        result.add_check(
            "成本预算",
            True,
            f"总成本 ¥{total_cost:.0f} 在预算 ¥{budget:.0f} 内 ✅"
        )

    return result
