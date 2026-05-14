"""
Tests for scheduler/rest_days.py — rest day recommendations
"""

from scheduler.rest_days import recommend_rest_days, validate_coverage


class TestRecommendRestDays:
    def test_three_employees(self):
        """3 employees, each gets 2 rest days"""
        result = recommend_rest_days(["张三", "李四", "王五"], 2)
        assert len(result) == 3
        for emp, days in result.items():
            assert len(days) == 2

    def test_employees_different_rest_days(self):
        """Different employees should have different rest days"""
        result = recommend_rest_days(["张三", "李四", "王五"], 2)
        # Some rest days should differ
        rest_sets = [set(days) for days in result.values()]
        # Not all employees should have identical rest days
        assert not all(s == rest_sets[0] for s in rest_sets[1:])

    def test_daily_coverage(self):
        """With 3 employees each resting 2 days, average coverage >= 2"""
        employees = ["张三", "李四", "王五"]
        result = recommend_rest_days(employees, 2)
        week_days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        coverage = validate_coverage(result, week_days)
        avg_coverage = sum(coverage.values()) / len(coverage)
        assert avg_coverage >= 2, f"Avg coverage {avg_coverage:.1f} < 2"
        # At most 2 days should have < 2 staff
        low_days = sum(1 for c in coverage.values() if c < 2)
        assert low_days <= 2, f"{low_days} days have < 2 staff"


class TestValidateCoverage:
    def test_coverage_count(self):
        rest_days = {
            "张三": ["周一"],
            "李四": ["周二"],
            "王五": [],
        }
        week_days = ["周一", "周二", "周三"]
        coverage = validate_coverage(rest_days, week_days)
        assert coverage["周一"] == 2  # 张三休息
        assert coverage["周二"] == 2  # 李四休息
        assert coverage["周三"] == 3  # 全部在岗

    def test_all_resting(self):
        rest_days = {"张三": ["周一"], "李四": ["周一"], "王五": ["周一"]}
        coverage = validate_coverage(rest_days, ["周一"])
        assert coverage["周一"] == 0
