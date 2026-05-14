"""
门店配置页
"""

import streamlit as st

st.set_page_config(page_title="门店配置", page_icon="📊")

st.title("📊 门店配置")
st.markdown("设置门店基本参数，这是排班的基础数据。")

# 门店基本信息
with st.expander("🏪 门店信息", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        store_name = st.text_input("门店名称", value="Gelato 门店")
        store_hours = st.slider("营业时间", 6, 24, (10, 22))
    with col2:
        employee_count = st.number_input("员工人数", min_value=1, max_value=50, value=3)
        service_type = st.selectbox("服务模式", ["纯堂食", "堂食+外卖", "纯外卖"])

# 产能参数
with st.expander("⚙️ 产能参数", expanded=True):
    st.markdown("""
    **产能公式**：最低在岗人数 = ⌈高峰客流 ÷ 单人产能⌉
    """)

    col1, col2 = st.columns(2)
    with col1:
        productivity = st.number_input(
            "单人产能（单/小时）",
            min_value=1,
            value=18,
            help="每人每小时能服务多少顾客"
        )
    with col2:
        peak_customers = st.number_input(
            "高峰客流量（单/小时）",
            min_value=1,
            value=60,
            help="高峰时段预估每小时客流量"
        )

# 高峰时段配置
with st.expander("📈 高峰时段", expanded=False):
    st.markdown("**工作日高峰**")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("午高峰", value="12:00-14:00")
    with col2:
        st.text_input("晚高峰", value="17:00-19:00")

    st.markdown("**周末高峰**")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("周末午高峰", value="11:00-14:00")
    with col2:
        st.text_input("周末晚高峰", value="16:00-20:00")

if st.button("💾 保存配置", type="primary"):
    st.success("配置已保存！")
    st.session_state["store_config"] = {
        "name": store_name,
        "hours": store_hours,
        "employees": employee_count,
        "productivity": productivity,
        "peak_customers": peak_customers,
    }
