# 导出排班结果功能设计

## 概述
为排班生成页面增加 Excel 导出功能，支持导出排班明细、周工时统计、月工时统计。

## 技术方案
- 使用 `pandas.DataFrame.to_excel()` + `pd.ExcelWriter` 生成 `.xlsx`
- 依赖 `openpyxl`（pandas 导出 xlsx 的默认引擎）
- 文件在内存中构建（`io.BytesIO`），通过 `st.download_button` 触发下载

## Sheet 结构

### Sheet 1: 排班明细
- 每行：员工、日期、班次、开始时间、结束时间
- 按周分组，周排班模式下仅 1 组，月排班模式下 4 组
- 格式：表头加粗，列宽自适应

### Sheet 2: 周工时统计
- 每行：员工、周次、周工时(h)、上限(h)、状态(OK/NG)
- 周排班模式：7 天数据，上限 54h
- 月排班模式：4 周数据合并

### Sheet 3: 月工时统计（仅月排班模式）
- 每行：员工、月总工时、扣除吃饭后工时、上限(h)、状态(OK/NG)
- 仅在月排班模式下生成

## UI
- 排班结果显示后，在 `st.success()` 消息后增加 `st.download_button`
- 按钮标签：`📥 导出 Excel`
- 文件名格式：`排班方案_{门店名}_{日期范围}.xlsx`
- 周排班：`排班方案_{门店名}_{周一起}.xlsx`
- 月排班：`排班方案_{门店名}_{月份}.xlsx`

## 代码实现
- 新增 `_export_to_excel()` 函数在 `pages/02_排班生成.py` 模块级
- 参数：`schedule_by_emp, week_days, emp_names, shifts, shift_map, all_weekly_results, schedule_mode, meal_break, config`
- 返回：`BytesIO` 对象
- 同时支持周排班（单周）和月排班（多周）两种模式

## 不变的部分
- 排班生成逻辑不变
- 不影响现有的周/月排班流程
