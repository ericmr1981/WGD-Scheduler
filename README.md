# WGD-Scheduler 🍦

Gelato 门店智能排班系统 — Streamlit + Supabase

## 项目简介

基于排班方法论总纲（目标体系→从零诊断→核心原则→执行流程→持续优化），将排班流程产品化为可交互的 Web 工具。

- **前端**：Streamlit
- **数据库**：Supabase (PostgreSQL)
- **认证**：Supabase Auth

## 项目结构

```
WGD-Scheduler/
├── app.py                 # Streamlit 主入口
├── pages/                 # Streamlit 多页面
│   ├── 01_门店配置.py
│   ├── 02_排班生成.py
│   ├── 03_排班检查.py
│   └── 04_复盘迭代.py
├── scheduler/             # 排班逻辑模块
│   ├── __init__.py
│   ├── core.py            # 产能公式、在岗人数计算
│   ├── peaks.py           # 高峰模型（平日/周末/节假日）
│   ├── shifts.py          # 班次生成（A/B/C 三班 + 轮换）
│   ├── rest_days.py       # 休息日安排
│   ├── validation.py      # 自动检查
│   └── iteration.py       # 参数迭代
├── db/                    # 数据库模块
│   ├── __init__.py
│   └── supabase.py        # Supabase 连接与操作
├── requirements.txt
├── .gitignore
└── .streamlit/config.toml
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行 Streamlit
streamlit run app.py
```

## 技术栈

- Python 3.10+
- Streamlit
- Supabase (PostgreSQL + Auth)
- supabase-py
