"""
WGD-Scheduler 🍦
Gelato 门店智能排班系统
Streamlit + Supabase
"""

import streamlit as st

from db.supabase_client import get_stores


def _parse_hour(time_val, default):
    if isinstance(time_val, str) and ":" in time_val:
        parts = time_val.split(":")
        return int(parts[0]) + int(parts[1]) / 60
    return default


def _build_config(store: dict) -> dict:
    return {
        "id": store["id"],
        "name": store["name"],
        "hours": (_parse_hour(store["open_time"], 10), _parse_hour(store["close_time"], 22)),
        "employees": store["employee_count"],
        "productivity": store["productivity_per_hour"],
        "productivity_a": store.get("productivity_a", 24),
        "productivity_b": store.get("productivity_b", 18),
        "productivity_c": store.get("productivity_c", 12),
        "productivity_other": store.get("productivity_other", 15),
        "peak_customers": store.get("peak_customers_per_hour", 60),
        "service_type": store.get("service_type", "纯堂食"),
        "peak_periods": {
            "weekday_lunch": store.get("weekday_lunch_peak", "12:00-14:00"),
            "weekday_dinner": store.get("weekday_dinner_peak", "17:00-19:00"),
            "weekend_lunch": store.get("weekend_lunch_peak", "11:00-14:00"),
            "weekend_dinner": store.get("weekend_dinner_peak", "16:00-20:00"),
        },
        "opening_prep_mins": store.get("opening_prep_mins", 60),
        "opening_staff_count": store.get("opening_staff_count", 1),
        "closing_tasks_mins": store.get("closing_tasks_mins", 60),
        "meal_break_mins": store.get("meal_break_mins", 30),
        "max_meals_per_employee": store.get("max_meals_per_employee", 1),
        "target_hours_per_employee": float(store.get("target_hours_per_employee", 8.0)),
        "min_staff_on_duty": store.get("min_staff_on_duty", 1),
    }


st.set_page_config(
    page_title="WGD-Scheduler",
    page_icon="🍦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ========== SSO 认证 ==========
import json, ssl, urllib.request

_sso_url, _sso_key = None, None
_sso_ctx = ssl.create_default_context()
_sso_ctx.check_hostname = False
_sso_ctx.verify_mode = ssl.CERT_NONE

try:
    _sso_url = (
        st.secrets.get("SUPABASE_URL", "")
        or st.secrets.get("supabase", {}).get("url", "")
    )
    _sso_key = (
        st.secrets.get("SUPABASE_ANON_KEY", "")
        or st.secrets.get("supabase", {}).get("anon_key", "")
        or st.secrets.get("SUPABASE_KEY", "")
    )
except Exception:
    pass

if "sso_user" not in st.session_state:
    params = st.query_params
    token = params.get("sso_token")
    if isinstance(token, list):
        token = token[0] if token else None
    token = str(token) if token else None

    if token and _sso_url and _sso_key:
        body = json.dumps({"p_token": token}).encode()
        req = urllib.request.Request(
            f"{_sso_url}/rest/v1/rpc/verify_sso_token",
            data=body,
            headers={
                "Content-Type": "application/json",
                "apikey": _sso_key,
                "Authorization": f"Bearer {_sso_key}",
            },
        )
        try:
            resp = urllib.request.urlopen(req, context=_sso_ctx)
            result = json.loads(resp.read().decode())
            if result.get("valid"):
                st.session_state.sso_user = result
                st.rerun()
        except Exception:
            pass

    if "sso_user" not in st.session_state or not st.session_state.sso_user:
        if token:
            st.error("# 未授权访问\n\n请通过公司 Portal 登录后访问。")
            st.stop()
        # 无 token 时放行（本地开发 / 直接访问）

_sso_url, _sso_key = None, None
# ========== SSO 认证结束 ==========

st.title("🍦 WGD-Scheduler")
st.markdown("---")

st.markdown("""
## Gelato 门店智能排班系统

基于 **排班方法论总纲**（目标体系→从零诊断→核心原则→执行流程→持续优化），
将排班流程产品化为可交互的工具。

### 使用流程

| 步骤 | 页面 | 功能说明 |
|------|------|---------|
| 1️⃣ | **门店配置** | 营业时间、员工数、出品类型产能(A/B/C/其他)、高峰时段、开早/打烊/用餐参数、班次时长、最低在岗人数 |
| 2️⃣ | **排班生成** | 输入日均客流，CP-SAT 求解器自动生成 **3 个最优排班方案**，含产能拟合曲线、甘特图、周工时统计 |
| 3️⃣ | **排班检查** | 检查每日覆盖、产能合规 |
| 📚 | **知识库** | 排班方法论总纲、操作手册、表格模板 |

### 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **CP-SAT 智能求解** | Google OR-Tools 约束求解器，按权重优化产能覆盖(1000) > 高峰覆盖(500) > 休息均匀(100) > 班次种类(1) |
| 🔄 **3 套备选方案** | 自动生成评分最高的 3 个排班方案，可折叠对比 |
| 📊 **产能拟合曲线** | 30 分钟颗粒度对比客流需求与员工总产量，含小时峰值参考线 |
| 📅 **甘特图展示** | 每日水平甘特图，直观显示每位员工的班次起止时间和类型 |
| ⏱ **员工周工时统计** | 自动统计每人周总工时，检查 54h 上限 |
| 🧩 **动态班次池** | 营业时间内所有可能的连续 9 小时班次(30min 颗粒度)，求解器择优选择 |
| 📈 **产能利用率** | 员工总产能 vs 总客流对比，评估拟合度 |
| 🎯 **高峰优先保障** | 高峰时段覆盖缺口权重 500，优先保证高峰期人力充足 |
| 🏪 **出品类型拆解** | 单人产能按 A/B/C/其他 四类出品分别设置，综合计算 |

### 求解器优先级

```
权重 1000 → 所有时段产能缺口最小化
权重  500 → 高峰时段产能缺口最小化（午/晚高峰）
权重  100 → 工作日休息日均匀分布
权重    1 → 使用班次种类最少化
```

### 快速开始
👉 从左侧菜单选择 **门店配置** 开始设置，然后进入 **排班生成** 查看优化结果。
""")

# 侧边栏信息
with st.sidebar:
    st.markdown("### 🏪 门店选择")
    stores = []
    try:
        stores = get_stores()
    except Exception:
        pass
    store_names = [s["name"] for s in stores]
    current_store = st.session_state.get("selected_store_name", store_names[0] if store_names else None)
    if store_names:
        idx = store_names.index(current_store) if current_store in store_names else 0
        selected = st.selectbox("选择门店", store_names, index=idx, key="store_selector", label_visibility="collapsed")
        if selected != st.session_state.get("selected_store_name"):
            st.session_state["selected_store_name"] = selected
            store = next(s for s in stores if s["name"] == selected)
            st.session_state["store_config"] = _build_config(store)
            st.session_state["store_id"] = store["id"]
            st.rerun()

    st.markdown("### 关于 WGD-Scheduler")
    st.markdown("版本：v1.1 | 排班优化引擎")
    st.markdown("---")
    st.markdown("**核心技术栈**")
    st.markdown("- **前端**：Streamlit + ECharts")
    st.markdown("- **求解器**：Google OR-Tools CP-SAT")
    st.markdown("- **数据库**：Supabase (PostgreSQL)")
    st.markdown("- **排班引擎**：Python + pandas")
    st.markdown("---")
    st.markdown("**排班约束**")
    st.markdown("- ✅ 周六日全员到岗")
    st.markdown("- ✅ 无连续休息")
    st.markdown("- ✅ 营业期不空缺")
    st.markdown("- ✅ 每人每天 ≤ 9h")
    st.markdown("- ✅ 每人每周 ≤ 54h")
