"""
门店配置页 — 带 Supabase 持久化
"""

import os
import json
import streamlit as st
from urllib.request import Request, urlopen
from db.supabase_client import get_stores, create_store, update_store, get_client

st.set_page_config(page_title="门店配置", page_icon="📊")

st.title("📊 门店配置")
st.markdown("设置门店基本参数，数据保存在云端，刷新不会丢失。")

# ─── Supabase 连接状态诊断 ──────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    client = get_client()
    if client is not None:
        st.info("✅ Supabase 已连接，数据将持久保存到云端。")
    else:
        # 诊断：检查配置是否存在
        supabase_url = ""
        supabase_key = ""
        try:
            supabase_url = st.secrets.get("SUPABASE_URL", "") or st.secrets.get("supabase", {}).get("url", "")
        except Exception:
            pass
        try:
            supabase_key = st.secrets.get("SUPABASE_ANON_KEY", "") or st.secrets.get("supabase", {}).get("anon_key", "")
        except Exception:
            pass
        if not supabase_url:
            supabase_url = os.environ.get("SUPABASE_URL", "")
        if not supabase_key:
            supabase_key = os.environ.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_KEY", "")

        if not supabase_url:
            st.error("❌ 未找到 SUPABASE_URL 配置")
        elif not supabase_key:
            st.error("❌ 未找到 SUPABASE_ANON_KEY 配置")
        else:
            # 有配置但连接失败，测试 HTTP 直连
            st.warning("⚠️ SDK 连接失败，正在测试 HTTP 直连…")
            try:
                req = Request(
                    f"{supabase_url.rstrip('/')}/rest/v1/stores",
                    headers={
                        "apikey": supabase_key,
                        "Authorization": f"Bearer {supabase_key}",
                    },
                )
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    st.success(f"✅ HTTP 直连成功！返回 {len(data)} 条数据。可正常使用。")
            except Exception as e:
                st.error(f"❌ HTTP 直连也失败: {e}")

with col2:
    if st.button("🔄 重试连接"):
        st.cache_data.clear()
        st.rerun()

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
    """从 '10:00' 或 '10:30:00' 格式提取小时数（float，30分钟颗粒度）。"""
    if isinstance(time_str, str) and ":" in time_str:
        parts = time_str.split(":")
        return int(parts[0]) + int(parts[1]) / 60
    return default

default_open = float(parse_hour(get_default("open_time", None), 10))
default_close = float(parse_hour(get_default("close_time", None), 22))
default_emp = get_default("employee_count", 3)
default_prod = get_default("productivity_per_hour", 18)
default_prod_a = get_default("productivity_a", 24)
default_prod_b = get_default("productivity_b", 18)
default_prod_c = get_default("productivity_c", 12)
default_prod_other = get_default("productivity_other", 15)
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

# 工时/就餐/在岗参数
default_opening_prep   = get_default("opening_prep_mins", 60)
default_closing_tasks  = get_default("closing_tasks_mins", 60)
default_meal_break     = get_default("meal_break_mins", 30)
default_max_meals      = get_default("max_meals_per_employee", 1)
default_target_hours   = float(get_default("target_hours_per_employee", 8.0))
default_min_staff      = get_default("min_staff_on_duty", 1)


# ─── 表单 ─────────────────────────────────────────────────────────

with st.expander("🏪 门店信息", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        store_name = st.text_input("门店名称", value=default_name)
        time_opts = [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in (0, 30)]
        def_idx = time_opts.index(f"{int(default_open):02d}:{int(default_open%1*60):02d}") if default_open else 8
        close_idx = time_opts.index(f"{int(default_close):02d}:{int(default_close%1*60):02d}") if default_close else 32
        open_str, close_str = st.select_slider(
            "营业时间", options=time_opts,
            value=(time_opts[def_idx], time_opts[close_idx]),
        )
        h1, m1 = open_str.split(":")
        h2, m2 = close_str.split(":")
        open_h = int(h1) + int(m1) / 60
        close_h = int(h2) + int(m2) / 60
    with col2:
        employee_count = st.number_input(
            "员工人数", min_value=1, max_value=50, value=default_emp
        )
        service_type = st.selectbox(
            "服务模式", svc_options, index=default_svc_idx
        )

with st.expander("⚙️ 产能参数", expanded=True):
    st.markdown("**产能公式**：最低在岗人数 = ⌈高峰客流 ÷ 综合单人产能⌉")
    st.markdown("按出品类型拆解单人产能，排班会使用加权平均。")
    cols = st.columns(4)
    with cols[0]:
        prod_a = st.number_input("出品A类（单/h）", min_value=1, value=default_prod_a,
                                  help="简易出品，如 cone/prepack")
    with cols[1]:
        prod_b = st.number_input("出品B类（单/h）", min_value=1, value=default_prod_b,
                                  help="常规出品，如 cup/shake")
    with cols[2]:
        prod_c = st.number_input("出品C类（单/h）", min_value=1, value=default_prod_c,
                                  help="复杂出品，如 sundae/affogato")
    with cols[3]:
        prod_other = st.number_input("其它（单/h）", min_value=1, value=default_prod_other,
                                      help="非标准化出品")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        peak_customers = st.number_input(
            "高峰客流量（单/小时）", min_value=1, value=default_peak,
            help="高峰时段预估每小时客流量"
        )
    with col2:
        # 计算综合产能
        avg_prod = int((prod_a + prod_b + prod_c + prod_other) / 4)
        st.metric("综合单人产能（自动计算）", f"{avg_prod} 单/h",
                  help="四种出品类型的算术平均")

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

with st.expander("⏰ 工时与员工参数", expanded=False):
    st.markdown("配置开早、打烊、就餐等营运参数，排班时会自动计算。")
    col1, col2 = st.columns(2)
    with col1:
        opening_prep = st.number_input(
            "开早所需时间（分钟）", min_value=0, max_value=180,
            value=default_opening_prep, step=5,
            help="开店前准备所需时间"
        )
        meal_break = st.number_input(
            "工作餐时间（分钟）", min_value=0, max_value=120,
            value=default_meal_break, step=5,
            help="每班次就餐时间，不计入8小时工时"
        )
        target_hours = st.number_input(
            "每位员工目标工时（小时/天）", min_value=1.0, max_value=12.0,
            value=default_target_hours, step=0.5,
            help="每位员工每天目标工作小时数（不含就餐时间）"
        )
    with col2:
        closing_tasks = st.number_input(
            "打烊所需时间（分钟）", min_value=0, max_value=180,
            value=default_closing_tasks, step=5,
            help="打烊后收尾所需时间"
        )
        max_meals = st.number_input(
            "每位员工每日最大就餐次数", min_value=0, max_value=3,
            value=default_max_meals,
            help="每位员工每天最多可以安排几次就餐"
        )
        min_on_duty = st.number_input(
            "最低在岗人数", min_value=1, max_value=20,
            value=default_min_staff,
            help="任何时间至少保持的在岗人数（安全底线）"
        )

# ─── 保存 ─────────────────────────────────────────────────────────

if st.button("💾 保存配置", type="primary"):
    store_data = {
        "name": store_name,
        "open_time": f"{int(open_h):02d}:{int(open_h % 1 * 60):02d}",
        "close_time": f"{int(close_h):02d}:{int(close_h % 1 * 60):02d}",
        "employee_count": employee_count,
        "service_type": service_type,
        "productivity_per_hour": int((prod_a + prod_b + prod_c + prod_other) / 4),
        "productivity_a": prod_a,
        "productivity_b": prod_b,
        "productivity_c": prod_c,
        "productivity_other": prod_other,
        "peak_customers_per_hour": peak_customers,
        "base_daily_customers": 200,
        "weekday_lunch_peak": week_lunch,
        "weekday_dinner_peak": week_dinner,
        "weekend_lunch_peak": weekend_lunch,
        "weekend_dinner_peak": weekend_dinner,
        "opening_prep_mins": opening_prep,
        "closing_tasks_mins": closing_tasks,
        "meal_break_mins": meal_break,
        "max_meals_per_employee": max_meals,
        "target_hours_per_employee": target_hours,
        "min_staff_on_duty": min_on_duty,
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
            "productivity": int((prod_a + prod_b + prod_c + prod_other) / 4),
            "productivity_a": prod_a,
            "productivity_b": prod_b,
            "productivity_c": prod_c,
            "productivity_other": prod_other,
            "peak_customers": peak_customers,
            "service_type": service_type,
            "peak_periods": {
                "weekday_lunch": week_lunch,
                "weekday_dinner": week_dinner,
                "weekend_lunch": weekend_lunch,
                "weekend_dinner": weekend_dinner,
            },
            "opening_prep_mins": opening_prep,
            "closing_tasks_mins": closing_tasks,
            "meal_break_mins": meal_break,
            "max_meals_per_employee": max_meals,
            "target_hours_per_employee": target_hours,
            "min_staff_on_duty": min_on_duty,
        }
        st.session_state["store_id"] = store_id
    except Exception as e:
        st.error(f"❌ 保存失败: {e}")
