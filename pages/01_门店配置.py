"""
门店配置页 — 带 Supabase 持久化
"""

import streamlit as st
from db.supabase_client import get_stores, create_store, update_store, get_client

st.set_page_config(page_title="门店配置", page_icon="📊")

st.title("📊 门店配置")
st.markdown("设置门店基本参数，数据保存在云端，刷新不会丢失。")

# ─── Supabase 连接状态 ────────────────────────────────────────────
client = get_client()
if client is None:
    st.warning("⚠️ Supabase 未连接，数据将仅在当前会话中生效，刷新后丢失。请检查 Supabase 配置。")
else:
    st.info("✅ Supabase 已连接，数据将持久保存到云端。")

# ─── 加载已有配置 ────────────────────────────────────────────────

def load_config():
    """从 Supabase 加载现有门店配置，返回 (store_id, data_dict) 或 (None, None)。"""
    try:
        stores = get_stores()
        if stores:
            s = stores[0]
            return s["id"], s
    except Exception as e:
        st.warning(f"⚠️ 数据库连接异常，使用本地默认值: {e}")
    return None, None

store_id, existing = load_config()

# ─── 提取默认值 ────────────────────────────────────────────────────

def get_default(key, default):
    """从现有配置取值，没有则返回默认值。"""
    if existing and key in existing:
        return existing[key]
    return default

def parse_hour(time_str, default):
    """从 '10:00' 格式提取小时数。"""
    if isinstance(time_str, str) and ":" in time_str:
        return int(time_str.split(":")[0])
    return default

default_open = parse_hour(get_default("open_time", None), 10)
default_close = parse_hour(get_default("close_time", None), 22)
default_emp = get_default("employee_count", 3)
default_prod = get_default("productivity_per_hour", 18)
default_peak = get_default("peak_customers_per_hour", 60)
default_svc = get_default("service_type", "纯堂食")
svc_options = ["纯堂食", "堂食+外卖", "纯外卖"]
default_svc_idx = svc_options.index(default_svc) if default_svc in svc_options else 0
default_name = get_default("name", "Gelato 门店")

# 高峰时段（可编辑）
default_wk_lunch  = get_default("weekday_lunch_peak", "12:00-14:00")
default_wk_dinner = get_default("weekday_dinner_peak", "17:00-19:00")
default_we_lunch  = get_default("weekend_lunch_peak", "11:00-14:00")
default_we_dinner = get_default("weekend_dinner_peak", "16:00-20:00")

# ─── 表单 ─────────────────────────────────────────────────────────

with st.expander("🏪 门店信息", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        store_name = st.text_input("门店名称", value=default_name)
        open_h, close_h = st.slider(
            "营业时间", 6, 24,
            value=(default_open, default_close)
        )
    with col2:
        employee_count = st.number_input(
            "员工人数", min_value=1, max_value=50, value=default_emp
        )
        service_type = st.selectbox(
            "服务模式", svc_options, index=default_svc_idx
        )

with st.expander("⚙️ 产能参数", expanded=True):
    st.markdown("**产能公式**：最低在岗人数 = ⌈高峰客流 ÷ 单人产能⌉")
    col1, col2 = st.columns(2)
    with col1:
        productivity = st.number_input(
            "单人产能（单/小时）", min_value=1, value=default_prod,
            help="每人每小时能服务多少顾客"
        )
    with col2:
        peak_customers = st.number_input(
            "高峰客流量（单/小时）", min_value=1, value=default_peak,
            help="高峰时段预估每小时客流量"
        )

with st.expander("📈 高峰时段", expanded=False):
    st.markdown("**工作日高峰**")
    col1, col2 = st.columns(2)
    with col1:
        week_lunch = st.text_input("午高峰", value=default_wk_lunch,
                                   help="格式如 12:00-14:00")
    with col2:
        week_dinner = st.text_input("晚高峰", value=default_wk_dinner,
                                    help="格式如 17:00-19:00")
    st.markdown("**周末高峰**")
    col1, col2 = st.columns(2)
    with col1:
        weekend_lunch = st.text_input("周末午高峰", value=default_we_lunch,
                                      help="格式如 11:00-14:00")
    with col2:
        weekend_dinner = st.text_input("周末晚高峰", value=default_we_dinner,
                                       help="格式如 16:00-20:00")

# ─── 保存 ─────────────────────────────────────────────────────────

if st.button("💾 保存配置", type="primary"):
    store_data = {
        "name": store_name,
        "open_time": f"{open_h:02d}:00",
        "close_time": f"{close_h:02d}:00",
        "employee_count": employee_count,
        "service_type": service_type,
        "productivity_per_hour": productivity,
        "peak_customers_per_hour": peak_customers,
        "base_daily_customers": 200,
        "weekday_lunch_peak": week_lunch,
        "weekday_dinner_peak": week_dinner,
        "weekend_lunch_peak": weekend_lunch,
        "weekend_dinner_peak": weekend_dinner,
    }

    try:
        if store_id:
            result = update_store(store_id, store_data)
            if result is None:
                st.error("❌ Supabase 未连接，无法更新。请检查 Supabase URL 和 Key 是否正确。")
            elif not result:
                st.error("❌ 更新失败：数据库返回空结果，请确认 stores 表已创建（运行 db/schema.sql）。")
            else:
                st.success("✅ 配置已更新到云！")
        else:
            created = create_store(store_data)
            if created is None:
                st.error("❌ Supabase 未连接，无法保存。请检查 Supabase URL 和 Key 是否正确。")
            elif not created:
                st.error("❌ 保存失败：数据库返回空结果，请确认 stores 表已创建（运行 db/schema.sql）。")
                st.stop()
            store_id = created.get("id")
            st.success("✅ 配置已保存到云！")

        # 同步到 session_state（供其他页面使用）
        st.session_state["store_config"] = {
            "id": store_id,
            "name": store_name,
            "hours": (open_h, close_h),
            "employees": employee_count,
            "productivity": productivity,
            "peak_customers": peak_customers,
            "service_type": service_type,
            "peak_periods": {
                "weekday_lunch": week_lunch,
                "weekday_dinner": week_dinner,
                "weekend_lunch": weekend_lunch,
                "weekend_dinner": weekend_dinner,
            },
        }
        st.session_state["store_id"] = store_id
    except Exception as e:
        st.error(f"❌ 保存失败: {e}")
