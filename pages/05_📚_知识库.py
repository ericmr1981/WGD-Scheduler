"""
知识库 — 排班方法论、操作手册、表格模板
"""

import streamlit as st
from pathlib import Path

st.set_page_config(page_title="知识库", page_icon="📚", layout="wide")

# ─── 样式 ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    .doc-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 1rem 0;
        line-height: 1.8;
        font-size: 16px;
    }
    .doc-container h1 {
        font-size: 1.8rem;
        border-bottom: 2px solid #f0c040;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
    }
    .doc-container h2 {
        font-size: 1.4rem;
        margin-top: 2rem;
        padding: 0.5rem 0;
        border-left: 4px solid #f0c040;
        padding-left: 0.75rem;
    }
    .doc-container h3 {
        font-size: 1.15rem;
        margin-top: 1.5rem;
    }
    .doc-container table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
        font-size: 14px;
    }
    .doc-container th {
        background: #f0c040;
        color: #1e1e1e;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
    }
    .doc-container td {
        padding: 8px 12px;
        border-bottom: 1px solid #333;
    }
    .doc-container tr:hover {
        background: #2a2a2a;
    }
    .doc-container blockquote {
        border-left: 4px solid #f0c040;
        margin: 1rem 0;
        padding: 0.5rem 1rem;
        background: #1e1e1e;
        border-radius: 0 8px 8px 0;
        color: #ccc;
    }
    .doc-container code {
        background: #2a2a2a;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
        color: #f0c040;
    }
    .doc-container pre {
        background: #1a1a1a;
        padding: 1rem;
        border-radius: 8px;
        overflow-x: auto;
        border: 1px solid #333;
        font-size: 13px;
    }
    .doc-container hr {
        border: none;
        border-top: 1px solid #333;
        margin: 2rem 0;
    }
    .toc-item {
        padding: 6px 0;
        cursor: pointer;
        font-size: 14px;
        color: #aaa;
        border-bottom: 1px solid #2a2a2a;
    }
    .toc-item:hover {
        color: #f0c040;
    }
    .toc-h3 {
        padding-left: 1rem;
        font-size: 13px;
    }
    .section-tag {
        display: inline-block;
        background: #f0c040;
        color: #1e1e1e;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        margin-right: 8px;
    }
    .doc-nav-btn {
        background: #2a2a2a;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 12px;
        margin: 4px 0;
        cursor: pointer;
        transition: all 0.2s;
    }
    .doc-nav-btn:hover {
        border-color: #f0c040;
        background: #333;
    }
    .doc-nav-btn.active {
        border-color: #f0c040;
        background: #1e1e1e;
    }
</style>
""", unsafe_allow_html=True)

# ─── 文档定义 ─────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"

DOCS = {
    "方法论总纲": {
        "file": "01-排班方法论总纲.md",
        "icon": "🧠",
        "desc": "排班核心理念、诊断流程、产能计算、决策树",
        "tag": "框架层",
    },
    "操作手册 v4.0": {
        "file": "02-操作手册-v3.0.md",
        "icon": "📖",
        "desc": "5步排班操作指引，Step-by-step",
        "tag": "执行层",
    },
    "表格模板 v2.1": {
        "file": "03-表格模板-v2.0.md",
        "icon": "📊",
        "desc": "5个工作表的结构说明和公式",
        "tag": "工具层",
    },
}

# ─── 侧边栏导航 ────────────────────────────────────────────────────

st.sidebar.title("📚 知识库")

selected_doc = None
for name, info in DOCS.items():
    is_active = st.sidebar.button(
        f"{info['icon']}  {name}",
        key=f"nav_{name}",
        use_container_width=True,
        type="secondary" if st.session_state.get("active_doc") != name else "primary",
    )
    if is_active:
        st.session_state["active_doc"] = name

# 默认选中第一个
if "active_doc" not in st.session_state:
    st.session_state["active_doc"] = list(DOCS.keys())[0]

active = st.session_state["active_doc"]
doc_info = DOCS[active]

# 文档描述
st.sidebar.markdown("---")
st.sidebar.markdown(f"**{doc_info['icon']} {active}**")
st.sidebar.caption(doc_info["desc"])
st.sidebar.markdown(f"<span class='section-tag'>{doc_info['tag']}</span>", unsafe_allow_html=True)

# 阅读提示
st.sidebar.markdown("---")
st.sidebar.caption("💡 点击左侧按钮切换文档")
st.sidebar.caption("使用浏览器搜索 (Cmd+F) 快速查找内容")

# ─── 阅读区域 ────────────────────────────────────────────────────

st.title(f"{doc_info['icon']} {active}")

# 读取 markdown 文件
doc_path = DOCS_DIR / doc_info["file"]
if not doc_path.exists():
    st.error(f"文档未找到: {doc_info['file']}")
    st.stop()

content = doc_path.read_text(encoding="utf-8")

# 在 st.markdown 中渲染
st.markdown(f'<div class="doc-container">', unsafe_allow_html=True)
st.markdown(content)
st.markdown("</div>", unsafe_allow_html=True)

# ─── 页脚导航 ─────────────────────────────────────────────────────

st.markdown("---")
doc_names = list(DOCS.keys())
current_idx = doc_names.index(active)

cols = st.columns(3)
with cols[0]:
    if current_idx > 0:
        prev_name = doc_names[current_idx - 1]
        if st.button(f"← {DOCS[prev_name]['icon']} {prev_name}", use_container_width=True):
            st.session_state["active_doc"] = prev_name
            st.rerun()

with cols[1]:
    st.markdown(
        f"<div style='text-align:center;color:#888;font-size:14px;padding:6px'>{current_idx + 1} / {len(DOCS)}</div>",
        unsafe_allow_html=True,
    )

with cols[2]:
    if current_idx < len(doc_names) - 1:
        next_name = doc_names[current_idx + 1]
        if st.button(f"{DOCS[next_name]['icon']} {next_name} →", use_container_width=True):
            st.session_state["active_doc"] = next_name
            st.rerun()
