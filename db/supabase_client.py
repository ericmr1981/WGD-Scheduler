"""
Supabase 客户端模块
支持 graceful fallback：配置缺失时不崩溃，只返回空数据并打印 warning
"""

import os
import warnings
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


_client: Optional[Client] = None


def _build_client() -> Optional[Client]:
    """
    依次尝试从以下来源读取 Supabase 配置，返回 client 或 None：
    1. st.secrets["SUPABASE_URL"] / st.secrets["SUPABASE_ANON_KEY"]   （Streamlit Cloud 扁平 keys）
    2. st.secrets["supabase"]["url"] / st.secrets["supabase"]["anon_key"]（本地 .streamlit/secrets.toml）
    3. 环境变量 SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_KEY
    """
    # 1. Streamlit secrets（Cloud 部署）
    try:
        import streamlit as st
        url = (
            st.secrets.get("SUPABASE_URL", "")
            or st.secrets.get("supabase", {}).get("url", "")
        )
        key = (
            st.secrets.get("SUPABASE_ANON_KEY", "")
            or st.secrets.get("supabase", {}).get("anon_key", "")
            or st.secrets.get("SUPABASE_KEY", "")
        )
        if url and key:
            return create_client(url, key)
    except Exception:
        pass

    # 2. 环境变量（本地开发）
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    if url and key:
        return create_client(url, key)

    return None


def get_client() -> Optional[Client]:
    """
    获取 Supabase 客户端（单例）。配置缺失时返回 None，不抛异常。
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def get_stores() -> list:
    """获取所有门店"""
    client = get_client()
    if client is None:
        warnings.warn("Supabase 未配置，返回空门店列表")
        return []
    return client.table("stores").select("*").execute().data or []


def get_store(store_id: str) -> dict:
    """获取单个门店"""
    client = get_client()
    if client is None:
        return {}
    data = client.table("stores").select("*").eq("id", store_id).execute().data
    return data[0] if data else {}


def create_store(store_data: dict) -> dict | None:
    """创建门店，返回新门店数据，无连接时返回 None"""
    client = get_client()
    if client is None:
        warnings.warn("Supabase 未配置，无法创建门店")
        return None
    data = client.table("stores").insert(store_data).execute().data
    return data[0] if data else {}


def update_store(store_id: str, store_data: dict) -> dict | None:
    """更新门店，返回更新后数据，无连接时返回 None"""
    client = get_client()
    if client is None:
        warnings.warn("Supabase 未配置，无法更新门店")
        return None
    data = (
        client.table("stores")
        .update(store_data)
        .eq("id", store_id)
        .execute()
        .data
    )
    return data[0] if data else {}


def get_employees(store_id: str) -> list:
    """获取门店员工列表"""
    client = get_client()
    if client is None:
        return []
    return client.table("employees").select("*").eq("store_id", store_id).execute().data or []


def create_employee(employee_data: dict) -> dict:
    """创建员工"""
    client = get_client()
    if client is None:
        return {}
    data = client.table("employees").insert(employee_data).execute().data
    return data[0] if data else {}


def save_schedule(schedule_data: dict) -> dict:
    """保存排班方案"""
    client = get_client()
    if client is None:
        return {}
    data = client.table("schedules").insert(schedule_data).execute().data
    return data[0] if data else {}


def get_schedules(store_id: str) -> list:
    """获取门店排班方案列表"""
    client = get_client()
    if client is None:
        return []
    return (
        client.table("schedules")
        .select("*")
        .eq("store_id", store_id)
        .order("week_start", desc=True)
        .execute()
        .data
        or []
    )


def save_shifts(shifts_data: list) -> list:
    """批量保存排班明细"""
    client = get_client()
    if client is None:
        return []
    return client.table("schedule_shifts").insert(shifts_data).execute().data or []


def save_review(review_data: dict) -> dict:
    """保存复盘记录"""
    client = get_client()
    if client is None:
        return {}
    data = client.table("weekly_reviews").insert(review_data).execute().data
    return data[0] if data else {}
