"""
Supabase 客户端模块
支持 SDK + HTTP 双通道 fallback：SDK 报错时自动降级到 HTTP 直连。
"""

import json
import os
import warnings
from typing import Optional
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

# ─── 凭据解析（模块级）─────────────────────────────────────────

_SUPABASE_URL = ""
_SUPABASE_KEY = ""

try:
    import streamlit as st
    _SUPABASE_URL = (
        st.secrets.get("SUPABASE_URL", "")
        or st.secrets.get("supabase", {}).get("url", "")
    )
    _SUPABASE_KEY = (
        st.secrets.get("SUPABASE_ANON_KEY", "")
        or st.secrets.get("supabase", {}).get("anon_key", "")
        or st.secrets.get("SUPABASE_KEY", "")
    )
except Exception:
    pass

if not _SUPABASE_URL:
    _SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
if not _SUPABASE_KEY:
    _SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_KEY", "")

# ─── HTTP 直连工具 ─────────────────────────────────────────────


def _http_get(path: str) -> list:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return []
    url = f"{_SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    req = Request(url, headers={
        "apikey": _SUPABASE_KEY, "Authorization": f"Bearer {_SUPABASE_KEY}",
    })
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()) or []
    except Exception:
        return []


def _http_post(path: str, data: dict) -> list:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return []
    body = json.dumps(data).encode()
    url = f"{_SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    req = Request(url, data=body, method="POST", headers={
        "apikey": _SUPABASE_KEY, "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()) or []
    except Exception:
        return []


def _http_patch(path: str, data: dict) -> list:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return []
    body = json.dumps(data).encode()
    url = f"{_SUPABASE_URL.rstrip('/')}/rest/v1/{path.lstrip('/')}"
    req = Request(url, data=body, method="PATCH", headers={
        "apikey": _SUPABASE_KEY, "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()) or []
    except Exception:
        return []


# ─── SDK 客户端（可选）─────────────────────────────────────────

_client: Optional[object] = None


def _build_client():
    url = _SUPABASE_URL
    key = _SUPABASE_KEY
    if url and key:
        try:
            from supabase import create_client
            return create_client(url, key)
        except Exception as e:
            warnings.warn(f"Supabase SDK client 创建失败: {e}")
    return None


def get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def is_connected() -> bool:
    return _client is not None or bool(_SUPABASE_URL and _SUPABASE_KEY)


# ─── 统一入口（SDK → HTTP fallback）────────────────────────────


def get_stores() -> list:
    client = get_client()
    if client is not None:
        try:
            return client.table("stores").select("*").execute().data or []
        except Exception as e:
            warnings.warn(f"SDK 查询失败，HTTP 直连: {e}")
    return _http_get("stores")


def get_store(store_id: str) -> dict:
    for s in get_stores():
        if s.get("id") == store_id:
            return s
    return {}


def create_store(store_data: dict) -> Optional[dict]:
    client = get_client()
    if client is not None:
        try:
            data = client.table("stores").insert(store_data).execute().data
            if data:
                return data[0]
        except Exception as e:
            warnings.warn(f"SDK 插入失败，HTTP 直连: {e}")
    result = _http_post("stores", store_data)
    return result[0] if result else None


def update_store(store_id: str, store_data: dict) -> Optional[dict]:
    client = get_client()
    if client is not None:
        try:
            data = (
                client.table("stores")
                .update(store_data)
                .eq("id", store_id)
                .execute()
                .data
            )
            if data:
                return data[0]
        except Exception as e:
            warnings.warn(f"SDK 更新失败，HTTP 直连: {e}")
    result = _http_patch(f"stores?id=eq.{store_id}", store_data)
    return result[0] if result else None


def get_employees(store_id: str) -> list:
    client = get_client()
    if client is not None:
        try:
            return (
                client.table("employees")
                .select("*")
                .eq("store_id", store_id)
                .execute()
                .data
                or []
            )
        except Exception:
            pass
    return _http_get(f"employees?store_id=eq.{store_id}")


def create_employee(employee_data: dict) -> dict:
    client = get_client()
    if client is not None:
        try:
            data = client.table("employees").insert(employee_data).execute().data
            return data[0] if data else {}
        except Exception:
            pass
    result = _http_post("employees", employee_data)
    return result[0] if result else {}


def save_schedule(schedule_data: dict) -> dict:
    client = get_client()
    if client is not None:
        try:
            data = client.table("schedules").insert(schedule_data).execute().data
            return data[0] if data else {}
        except Exception:
            pass
    result = _http_post("schedules", schedule_data)
    return result[0] if result else {}


def get_schedules(store_id: str) -> list:
    client = get_client()
    if client is not None:
        try:
            return (
                client.table("schedules")
                .select("*")
                .eq("store_id", store_id)
                .order("week_start", desc=True)
                .execute()
                .data
                or []
            )
        except Exception:
            pass
    return _http_get(f"schedules?store_id=eq.{store_id}&order=week_start.desc")


def save_shifts(shifts_data: list) -> list:
    client = get_client()
    if client is not None:
        try:
            return client.table("schedule_shifts").insert(shifts_data).execute().data or []
        except Exception:
            pass
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        return []
    body = json.dumps(shifts_data).encode()
    url = f"{_SUPABASE_URL.rstrip('/')}/rest/v1/schedule_shifts"
    req = Request(url, data=body, method="POST", headers={
        "apikey": _SUPABASE_KEY, "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()) or []
    except Exception:
        return []


def save_review(review_data: dict) -> dict:
    client = get_client()
    if client is not None:
        try:
            data = client.table("weekly_reviews").insert(review_data).execute().data
            return data[0] if data else {}
        except Exception:
            pass
    result = _http_post("weekly_reviews", review_data)
    return result[0] if result else {}
