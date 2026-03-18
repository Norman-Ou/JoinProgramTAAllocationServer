# JoinProgram TA Allocation Solver

基于整数线性规划（ILP / 分支定界法）的助教排班工具。将 19 名内部人员分配到 4 个日期共 24 个并发岗位，目标是最小化个人工作量的最大-最小差值（workload spread）。当内部人员不足时，自动报告各岗位需要补充的外部人数。

## 问题规模

| 项目 | 数值 |
|------|------|
| 内部人员 | 19 人 |
| 排班日期 | 4 天（3/15、4/12、5/24、5/31） |
| 岗位数量 | 24 个（每天 6 个，分上午/下午两批） |
| 总需求人次 | 120 |

## 约束条件

- **并发冲突**：同一时段的 3 个岗位同时进行，每人至多参与其中 1 个
- **跨时段冲突**：若上午与下午时段有时间重叠，每人当天至多参与 1 个时段
- **不可用约束**：
  - Yan、Dan、Kaiyang、Chenyue、Tongjia：不参加 3 月 15 日全天
  - Shuyue：不参加 3 月 15 日上午（可参加下午）
  - Xiaorun：不参加 4 月 12 日全天

## 求解方法

两阶段 ILP（均使用 CBC solver）：

1. **Phase 1**：最小化外部人员总数
2. **Phase 2**：固定外部人员总数，最小化 workload spread（W_max − W_min）

## 安装与运行

需要 [uv](https://docs.astral.sh/uv/)。

```bash
# 安装依赖
uv sync

# 运行排班
uv run paiban
```

## 输出示例

```
===== SCHEDULE =====
Job  1  Mar 15  1pm-3pm       need 7: [4 internal: Ruizhe, Yuxuan, ...], [3 external]
Job  7  Apr 12  1pm-3:30pm    need 7: [7 internal: Yuxuan, Tongjia, ...]
...

===== WORKLOAD SUMMARY =====
Person         Assignments
----------------------------
Ruizhe                   6
Yuxuan                   7
...
W_max=7, W_min=6, Spread=1

===== EXTERNAL HIRE NEEDS =====
Job  1  Mar 15  1pm-3pm       3 external

Total external needed: 3
```

## 依赖

- [PuLP](https://coin-or.github.io/pulp/) — Python ILP 建模库，底层使用 CBC solver
