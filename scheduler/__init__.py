"""
WGD-Scheduler — Gelato 门店智能排班系统

排班逻辑模块。包含：
- core: 产能公式、在岗人数计算
- peaks: 高峰模型（平日/周末/节假日）
- shifts: A/B/C 三班 + 轮换机制
- rest_days: 休息日安排
- validation: 自动检查与验证
- iteration: 周复盘与参数迭代
- models: Pydantic 数据模型
- supabase_client: 持久化存储客户端
"""

__version__ = "0.1.0"
