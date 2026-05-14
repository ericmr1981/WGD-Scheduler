# CP-SAT 排班求解器设计

## 问题描述

Gelato 门店排班：在多个运营约束下，为每位员工分配每日班次（A/B/C/休息），使排班方案最优。

## 输入

从门店配置页面读取的参数：
- 营业时间（open_hour, close_hour，30分钟颗粒度）
- 员工人数
- 单人产能（单/小时）
- 高峰时段及预估客流
- 开早/打烊时长
- 用餐时长 & 目标工时
- A/B/C 班次起止时间

客流预估：用户输入的日均客流量，按高峰时段分布计算为 30 分钟颗粒度。

## 硬约束

1. **营业期无空缺**：任何 30 分钟时段，在岗人数 ≥ 1
2. **每人每天 ≤ 9h**：在岗时长（含用餐）≤ 9 小时
3. **周末全员到岗**：周六、周日所有员工不得休息
4. **无连续休息**：休息日前后一天不能是休息日

## 软约束（优化目标，按优先级）

1. **产能覆盖率**（权重 1000）：每个 30 分钟时段 `缺口 = max(0, 预估客流 - 在岗人数 × 单人产能)`，所有时段缺口总和最小
2. **班次种类最少**（权重 1）：整周使用的不同班次（A/B/C）数量最少

组合目标：`minimize(1000 × 总缺口 + 班次种类数)`

## 求解模型

使用 Google OR-Tools CP-SAT 求解器。

### 变量

```
shift[employee][day] ∈ {0, 1, 2, 3}
  where 0=休息, 1=A班, 2=B班, 3=C班
```

### 辅助变量

```
on_duty[employee][day][slot] ∈ {0, 1}
  员工在 day 的 slot 时段是否在岗
  （由 shift 变量 + 班次时间推导，通过 CP-SAT 的 channeling 约束关联）
```

### 约束实现

1. 营业期覆盖：
```
  for each slot in operating_hours:
    sum(employee, on_duty[e][d][slot]) >= 1
```

2. 工时上限：
```
  for each employee, day:
    sum(slot, on_duty[e][d][slot]) * 0.5 <= 9.0
```

3. 周末全员：
```
  for each employee:
    shift[e][周六] != 0
    shift[e][周日] != 0
```

4. 无连续休息（含周跨日）：
```
  for each employee, day in [周一..周六]:
    if shift[e][day] == 0 then shift[e][day+1] != 0
```
  注：`day+1` 从周一→周二到周六→周日，周日休息不影响周一（已由规则 3 保证周日不休息）。

### on_duty 关联约束

每个员工的 `on_duty` 变量由 `shift` 变量和该班次的时间范围共同决定：

```
for each employee e, day d, 30min slot s:
  if shift[e][d] == A  and slot in A班时段 → on_duty[e][d][s] = 1
  if shift[e][d] == B  and slot in B班时段 → on_duty[e][d][s] = 1
  if shift[e][d] == C  and slot in C班时段 → on_duty[e][d][s] = 1
  if shift[e][d] == 休息 → on_duty[e][d][s] = 0
```

实现上用 CP-SAT 的 `OnlyEnforceIf` 或线性不等式。

### 目标函数

**缺口 gap 建模**（CP-SAT 不支持直接 max，用辅助变量）：

```
for each day d, slot s:
  gap_var[d][s] = model.NewIntVar(0, max_demand, f"gap_{d}_{s}")
  coverage = sum(on_duty[e][d][s] for e) * productivity
  model.Add(gap_var[d][s] >= demand[d][s] - coverage)
  model.Add(gap_var[d][s] >= 0)  # 隐含为下限
```

**班次种类建模**（用指示变量追踪是否使用了某班次）：

```
uses_A = model.NewBoolVar("uses_A")
uses_B = model.NewBoolVar("uses_B")
uses_C = model.NewBoolVar("uses_C")
# 如果任意员工任意天使用了 A，则 uses_A = True
for all e, d: model.Add(shift[e][d] == 1).OnlyEnforceIf(uses_A)
# 对称处理 B、C
shift_type_count = uses_A + uses_B + uses_C
```

**组合目标：**
```python
model.Minimize(1000 * sum(gap_var) + shift_type_count)
```

## 输出

```python
{
  "schedule": {employee: {day: shift_name_or_none}},
  "coverage_report": [
    {"day": "周一", "slots": [{"time": "09:00", "staff": 2, "gap": 5}, ...]},
    ...
  ],
  "objective_value": 123,
  "status": "OPTIMAL" | "FEASIBLE" | "INFEASIBLE",
}
```

## 集成方式

### 新增文件
- `scheduler/optimizer.py` — CP-SAT 求解器实现
- `requirements.txt` — 添加 `ortools>=9.11`

### 修改文件
- `pages/02_排班生成.py` — 用求解器替换规则排班
  - 保留客流分布图（不变）
  - 保留输入参数面板（不变）
  - 替换"生成排班方案"按钮后的逻辑

### Fallback
- 如果 `ortools` 导入失败，自动回退到当前规则算法
- `get_half_hourly_coverage()` 函数继续保留供 fallback 使用

## 测试策略

- 单元测试：`tests/test_optimizer.py`
  - 3 人场景验证所有硬约束
  - 4 人场景验证班次缩减
  - 验证周末全员约束
  - 验证缺口计算正确性
