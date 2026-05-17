"""
Traffic Analyzer — compute 30-minute customer traffic from product_sales data.

Pipeline:
    raw rows -> group_by_slots -> average_by_weekday_type -> build_demand_30min
"""

from collections import defaultdict
from datetime import date, datetime
from typing import Union

# ─── helper: time slot flooring ───────────────────────────────────────


def get_time_slot(order_time: Union[str, datetime]) -> str:
    """Floor a timestamp to the nearest 30-minute slot.

    Args:
        order_time: A datetime object, "HH:MM" string, or full ISO/space-separated string.

    Returns:
        Slot string like "12:00", "12:30".
    """
    if isinstance(order_time, datetime):
        hour, minute = order_time.hour, order_time.minute
    else:
        parsed = _parse_datetime(order_time)
        if parsed is not None:
            hour, minute = parsed.hour, parsed.minute
        else:
            # Fallback: try "HH:MM" only
            parts = order_time.strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

    floored = minute // 30 * 30
    return f"{hour:02d}:{floored:02d}"


def _parse_datetime(s: str):
    """Try common datetime string formats. Returns datetime or None."""
    import re as _re

    # Strip timezone offset like "+00", "+08:00", "-05:00"
    # so "2026-03-01 12:14:25+00" becomes "2026-03-01 12:14:25"
    s = _re.sub(r"[+-]\d{2}(:\d{2})?$", "", s.strip())

    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ─── grouping ─────────────────────────────────────────────────────────


def group_by_slots(rows: list[dict]) -> dict[tuple[str, str], set[str]]:
    """Group order numbers by (date, time_slot).

    Each row must have 'order_no' and 'order_time' keys.
    Returns a dict mapping (date_str, time_slot) -> set of unique order_nos.
    """
    result: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        order_no = row["order_no"]
        raw_time = row["order_time"]
        slot = get_time_slot(raw_time)
        date_str = _extract_date(raw_time)
        result[(date_str, slot)].add(order_no)
    return dict(result)


def _extract_date(raw_time) -> str:
    """Extract YYYY-MM-DD from a datetime string or object."""
    if isinstance(raw_time, datetime):
        return raw_time.strftime("%Y-%m-%d")
    parsed = _parse_datetime(raw_time)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")
    # If only time is given, return today
    return date.today().isoformat()


# ─── averaging ────────────────────────────────────────────────────────


def average_by_weekday_type(
    grouped: dict[tuple[str, str], set[str]],
) -> dict[str, dict[str, float]]:
    """Average unique order counts by weekday type.

    Returns:
        {"weekday": {"10:00": 5.0, ...}, "weekend": {"10:00": 3.0, ...}}
    """
    # Categorize each unique date
    weekday_dates: set[str] = set()
    weekend_dates: set[str] = set()

    for (date_str, _slot), _orders in grouped.items():
        dt = _date_from_str(date_str)
        if dt.weekday() < 5:
            weekday_dates.add(date_str)
        else:
            weekend_dates.add(date_str)

    # Sum order counts by slot and day type
    weekday_sums: dict[str, int] = defaultdict(int)
    weekend_sums: dict[str, int] = defaultdict(int)

    for (date_str, slot), orders in grouped.items():
        count = len(orders)
        dt = _date_from_str(date_str)
        if dt.weekday() < 5:
            weekday_sums[slot] += count
        else:
            weekend_sums[slot] += count

    num_weekdays = len(weekday_dates) or 1
    num_weekends = len(weekend_dates) or 1

    return {
        "weekday": {s: t / num_weekdays for s, t in weekday_sums.items()},
        "weekend": {s: t / num_weekends for s, t in weekend_sums.items()},
    }


def _date_from_str(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


# ─── demand builder ───────────────────────────────────────────────────


def build_demand_30min(
    avg_data: dict[str, dict[str, float]],
    week_days: list[str],
    open_hour: int = 10,
    close_hour: int = 22,
) -> dict[str, dict[str, int]]:
    """Build demand_30min dict for each day of a scheduling week.

    Args:
        avg_data: Output of average_by_weekday_type.
        week_days: List of day names (e.g. ["周一", "周二", ..., "周日"]).
        open_hour: Opening hour (default 10).
        close_hour: Closing hour (default 22).

    Returns:
        {"周一": {"10:00": 5, "10:30": 3, ...}, ...}
    """
    slots = _generate_slots(open_hour, close_hour)
    weekday_avg = avg_data.get("weekday", {})
    weekend_avg = avg_data.get("weekend", {})
    fallback_weekend = not weekend_avg

    result: dict[str, dict[str, int]] = {}
    for i, day_name in enumerate(week_days):
        is_weekend = i >= 5  # first 5 are weekdays
        template = weekend_avg if is_weekend and not fallback_weekend else weekday_avg
        result[day_name] = {slot: int(template.get(slot, 0.0)) for slot in slots}
    return result


def _generate_slots(open_hour: int, close_hour: int) -> list[str]:
    """Generate half-hour time slots from open_hour to close_hour (exclusive)."""
    slots = []
    total_minutes = open_hour * 60
    end_minutes = close_hour * 60
    while total_minutes < end_minutes:
        h, m = divmod(total_minutes, 60)
        slots.append(f"{h:02d}:{m:02d}")
        total_minutes += 30
    return slots


# ─── full pipeline ────────────────────────────────────────────────────


def get_actual_traffic(
    store_name: str,
    week_days: list[str],
    open_hour: int = 10,
    close_hour: int = 22,
) -> dict[str, dict[str, int]]:
    """Full pipeline: fetch product_sales -> group -> average -> build demand.

    Returns {} if no data is found or the fetch fails.
    """
    try:
        from db.supabase_client import get_product_sales
    except ImportError:
        return {}

    rows = get_product_sales(store_name)
    if not rows:
        return {}

    grouped = group_by_slots(rows)
    avg_data = average_by_weekday_type(grouped)
    return build_demand_30min(avg_data, week_days, open_hour, close_hour)
