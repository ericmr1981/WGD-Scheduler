"""
Supabase 客户端模块
"""

import os
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


_client: Optional[Client] = None


def get_client() -> Client:
    """
    获取 Supabase 客户端（单例）

    需要设置环境变量：
    - SUPABASE_URL
    - SUPABASE_ANON_KEY
    或在 .streamlit/secrets.toml 中配置
    """
    global _client

    if _client is not None:
        return _client

    # 优先从 Streamlit secrets 读取
    try:
        import streamlit as st
        url = st.secrets.get("supabase", {}).get("url", "")
        key = st.secrets.get("supabase", {}).get("anon_key", "")
    except Exception:
        url = ""
        key = ""

    # 其次从环境变量读取
    if not url:
        url = os.environ.get("SUPABASE_URL", "")
    if not key:
        key = os.environ.get("SUPABASE_ANON_KEY", "")

    if not url or not key:
        raise ValueError(
            "缺少 Supabase 配置。请在 .streamlit/secrets.toml 或环境变量中设置 "
            "SUPABASE_URL 和 SUPABASE_ANON_KEY"
        )

    _client = create_client(url, key)
    return _client


def get_stores() -> list:
    """获取所有门店"""
    client = get_client()
    response = client.table("stores").select("*").execute()
    return response.data


def get_store(store_id: str) -> dict:
    """获取单个门店"""
    client = get_client()
    response = client.table("stores").select("*").eq("id", store_id).execute()
    return response.data[0] if response.data else {}


def create_store(store_data: dict) -> dict:
    """创建门店"""
    client = get_client()
    response = client.table("stores").insert(store_data).execute()
    return response.data[0] if response.data else {}


def update_store(store_id: str, store_data: dict) -> dict:
    """更新门店"""
    client = get_client()
    response = (
        client.table("stores")
        .update(store_data)
        .eq("id", store_id)
        .execute()
    )
    return response.data[0] if response.data else {}


def get_employees(store_id: str) -> list:
    """获取门店员工列表"""
    client = get_client()
    response = (
        client.table("employees")
        .select("*")
        .eq("store_id", store_id)
        .execute()
    )
    return response.data


def create_employee(employee_data: dict) -> dict:
    """创建员工"""
    client = get_client()
    response = client.table("employees").insert(employee_data).execute()
    return response.data[0] if response.data else {}


def save_schedule(schedule_data: dict) -> dict:
    """保存排班方案"""
    client = get_client()
    response = client.table("schedules").insert(schedule_data).execute()
    return response.data[0] if response.data else {}


def get_schedules(store_id: str) -> list:
    """获取门店排班方案列表"""
    client = get_client()
    response = (
        client.table("schedules")
        .select("*")
        .eq("store_id", store_id)
        .order("week_start", desc=True)
        .execute()
    )
    return response.data


def save_shifts(shifts_data: list) -> list:
    """批量保存排班明细"""
    client = get_client()
    response = client.table("schedule_shifts").insert(shifts_data).execute()
    return response.data


def save_review(review_data: dict) -> dict:
    """保存复盘记录"""
    client = get_client()
    response = client.table("weekly_reviews").insert(review_data).execute()
    return response.data[0] if response.data else {}
