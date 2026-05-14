"""
Tests for scheduler/validation.py — schedule validation
"""

from scheduler.validation import validate_coverage, ValidationResult


class TestValidationResult:
    def test_all_passed(self):
        result = ValidationResult()
        result.add_check("检查1", True, "通过")
        result.add_check("检查2", True, "通过")
        assert result.all_passed() is True
        s = result.summary()
        assert s["total"] == 2
        assert s["passed"] == 2
        assert s["failed"] == 0

    def test_some_failed(self):
        result = ValidationResult()
        result.add_check("检查1", True, "通过")
        result.add_check("检查2", False, "失败")
        assert result.all_passed() is False
        s = result.summary()
        assert s["passed"] == 1
        assert s["failed"] == 1


class TestValidateCoverage:
    def test_all_covered(self):
        """All hours have >= 2 staff"""
        hourly = [2, 2, 3, 3, 2, 2, 3, 3, 2, 2, 2, 2]
        result = validate_coverage(hourly, min_required=2, peak_hours=[12, 13])
        assert result.all_passed() is True

    def test_understaffed_triggers_failure(self):
        """Hour 2 (12:00) has only 1 staff"""
        hourly = [2, 2, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        result = validate_coverage(hourly, min_required=2, peak_hours=[12, 13])
        assert result.all_passed() is False

    def test_peak_understaffed(self):
        """Peak hour 12:00 has only 2 staff (< 3)"""
        hourly = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
        result = validate_coverage(hourly, min_required=2, peak_hours=[12, 13])
        # min_required + 1 = 3 for peak
        assert result.all_passed() is False

    def test_all_hours_zero(self):
        """No staff at all should be caught"""
        hourly = [0] * 12
        result = validate_coverage(hourly, min_required=2, peak_hours=[12])
        assert result.all_passed() is False
