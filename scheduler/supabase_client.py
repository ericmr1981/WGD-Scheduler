"""
WGD Scheduler — Supabase Client

Provides a Supabase-backed data access layer, with a pure SQLite/JSON
fallback for local development when SUPABASE_URL/SUPABASE_KEY are not set.

Environment variables:
    SUPABASE_URL     — Supabase project URL
    SUPABASE_KEY     — Supabase anon/service key

If neither is set, the client operates in "local mode" using JSON files
under a .data/ directory within the project root.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .models import StoreConfig, Employee, ReviewData

# ─── JSON-encoder for date/datetime ────────────────────────────────


class _JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date and datetime objects."""
    def default(self, o: Any) -> Any:
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)


# ─── Supabase client (optional) ───────────────────────────────────

_SUPABASE_AVAILABLE = False
_supabase = None

SUPABASE_URL = ""
SUPABASE_KEY = ""

# 1. Streamlit secrets（Cloud 部署）
try:
    import streamlit as st
    SUPABASE_URL = (
        st.secrets.get("SUPABASE_URL", "")
        or st.secrets.get("supabase", {}).get("url", "")
    )
    SUPABASE_KEY = (
        st.secrets.get("SUPABASE_ANON_KEY", "")
        or st.secrets.get("supabase", {}).get("anon_key", "")
        or st.secrets.get("SUPABASE_KEY", "")
    )
except Exception:
    pass

# 2. 环境变量（本地开发）
if not SUPABASE_URL:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
if not SUPABASE_KEY:
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")

if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        _SUPABASE_AVAILABLE = True
    except Exception:
        _SUPABASE_AVAILABLE = False


# ─── Local storage (JSON file based) ──────────────────────────────

_DATA_DIR = Path(__file__).resolve().parent.parent / ".data"


def _ensure_data_dir():
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _local_save(collection: str, data: list[dict]) -> None:
    _ensure_data_dir()
    path = _DATA_DIR / f"{collection}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, cls=_JSONEncoder)


def _local_load(collection: str) -> list[dict]:
    path = _DATA_DIR / f"{collection}.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Public API ───────────────────────────────────────────────────


def is_connected() -> bool:
    """Check if Supabase is configured and reachable."""
    return _SUPABASE_AVAILABLE


def get_backend_name() -> str:
    """Return the active backend name for display."""
    if _SUPABASE_AVAILABLE:
        return "Supabase (云)"
    return "本地文件存储"


# ─── Store config ──────────────────────────────────────────────────


def save_store_config(config: StoreConfig, user_id: str = "default") -> None:
    """Save or update the store configuration."""
    data = config.model_dump()
    data["user_id"] = user_id
    data["updated_at"] = datetime.now().isoformat()

    if _SUPABASE_AVAILABLE:
        _supabase.table("store_configs").upsert(
            data, on_conflict="user_id"
        ).execute()
    else:
        records = _local_load("store_configs")
        # Replace existing record for this user
        records = [r for r in records if r.get("user_id") != user_id]
        records.append(data)
        _local_save("store_configs", records)


def load_store_config(user_id: str = "default") -> Optional[StoreConfig]:
    """Load the store configuration for a user."""
    if _SUPABASE_AVAILABLE:
        result = _supabase.table("store_configs").select("*").eq(
            "user_id", user_id
        ).execute()
        if result.data:
            return StoreConfig(**result.data[0])
        return None
    else:
        records = _local_load("store_configs")
        for r in records:
            if r.get("user_id") == user_id:
                return StoreConfig(**r)
        return None


# ─── Employees ─────────────────────────────────────────────────────


def save_employees(
    employees: list[Employee], user_id: str = "default"
) -> None:
    """Save the employee list."""
    data = [e.model_dump() | {"user_id": user_id} for e in employees]

    if _SUPABASE_AVAILABLE:
        # Delete existing, re-insert
        _supabase.table("employees").delete().eq(
            "user_id", user_id
        ).execute()
        _supabase.table("employees").insert(data).execute()
    else:
        _local_save("employees", data)


def load_employees(user_id: str = "default") -> list[Employee]:
    """Load the employee list for a user."""
    if _SUPABASE_AVAILABLE:
        result = _supabase.table("employees").select("*").eq(
            "user_id", user_id
        ).execute()
        return [Employee(**r) for r in result.data]
    else:
        records = _local_load("employees")
        return [
            Employee(**r) for r in records if r.get("user_id") == user_id
        ]


# ─── Review data ───────────────────────────────────────────────────


def save_review(review: ReviewData, user_id: str = "default") -> None:
    """Save a weekly review record."""
    data = review.model_dump()
    data["user_id"] = user_id
    data["created_at"] = datetime.now().isoformat()

    if _SUPABASE_AVAILABLE:
        _supabase.table("reviews").insert(data).execute()
    else:
        records = _local_load("reviews")
        records.append(data)
        _local_save("reviews", records)


def load_reviews(
    user_id: str = "default", limit: int = 10
) -> list[ReviewData]:
    """Load recent weekly reviews for a user."""
    if _SUPABASE_AVAILABLE:
        result = _supabase.table("reviews").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(limit).execute()
        return [ReviewData(**r) for r in result.data]
    else:
        records = _local_load("reviews")
        filtered = [
            r for r in records if r.get("user_id") == user_id
        ]
        # Sort by week_start descending
        filtered.sort(
            key=lambda r: r.get("week_start", ""), reverse=True
        )
        return [ReviewData(**r) for r in filtered[:limit]]
