"""
WGD-Scheduler 🍦
Gelato 门店智能排班系统
Streamlit + Supabase
"""

import streamlit as st

st.set_page_config(
    page_title="WGD-Scheduler",
    page_icon="🍦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🍦 WGD-Scheduler")
st.markdown("---")

st.markdown("""
## Gelato 门店智能排班系统

基于 **排班方法论总纲**（目标体系→从零诊断→核心原则→执行流程→持续优化），
将排班流程产品化为可交互的工具。

### 使用流程
| 步骤 | 页面 | 说明 |
|------|------|------|
| 1️⃣ | **门店配置** | 设置营业时间、员工数、单人产能等参数 |
| 2️⃣ | **排班生成** | 输入客流预估 → 自动算需求人数 → 生成排班表 |
| 3️⃣ | **排班检查** | 人工/自动检查覆盖、产能、合规 |
| 4️⃣ | **复盘迭代** | 每周复盘，修正产能参数 |

### 快速开始
👉 从左侧菜单选择 **门店配置** 开始
""")

# 侧边栏信息
with st.sidebar:
    st.markdown("### 关于 WGD-Scheduler")
    st.markdown("版本：MVP v0.1")
    st.markdown("---")
    st.markdown("**技术栈**")
    st.markdown("- Streamlit")
    st.markdown("- Supabase")
    st.markdown("- Python")
