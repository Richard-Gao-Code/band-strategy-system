# 导航结构

## 整体布局

```
┌───────────────────────────────────────────────────────────────────────────┐
│ 顶部导航栏（Header）                                                      │
│  Logo / 产品名 | 扫描 配置 回测 池子 日记 交易分析 日志 数据 任务 选股 调试  │
│                                                    主题切换（暗色/亮色）    │
├───────────────────────────────────────────────────────────────────────────┤
│ 主内容区（Main，max-width 1600px，居中）                                   │
│  根据当前 view-* 显示对应模块内容（其它 view-* 使用 .hidden 隐藏）          │
└───────────────────────────────────────────────────────────────────────────┘
```

## 视图与导航映射

顶栏按钮通过 `onclick="setActiveView('xxx')"` 切换视图（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L160-L178) 与 [setActiveView](file:///f:/Projects/band-strategy/static_bak/app.js#L2439-L2465)）。

| 菜单 | viewId | DOM 入口 | 说明 |
|------|--------|----------|------|
| 扫描 | `scan` | `#view-scan` | 扫描配置 + 扫描结果表格 |
| 配置 | `config` | `#view-config` | 预设管理 + 参数编辑 + 参数说明 |
| 回测 | `backtest` | `#view-backtest` | 批量回测 + 筛选排序 + 详情弹窗 + 批量参数测试 |
| 池子 | `pool` | `#view-pool` | 明星池 CRUD、池子扫描/回测、监控（本地保存） |
| 日记 | `journal` | `#view-journal` | 交易记录表单 + 列表（本地保存） |
| 交易分析 | `analysis` | `#view-analysis` | 智能分析入口（问答/解释） |
| 日志 | `logs` | `#view-logs` | 运行日志输出区（前端缓冲） |
| 数据 | `data` | `#view-data` | 数据文件列表 + 同步 + 质量检查 |
| 任务 | `tasks` | `#view-tasks` | 定时更新（数据同步调度）与运行状态 |
| 选股决策 | `selector` | `#view-selector` | 一键选股 + 结果展示 |
| 策略调试 | `debug` | `#view-debug` | 单标的调试分析（overview/trades/features） |

## 默认进入视图

- 首屏 DOM 中 `#view-scan` 默认不带 `.hidden`，其它 view 初始为 `.hidden`（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L189-L200)）。
- 视图切换仅影响 UI 显隐，不改变 URL；页面刷新后会回到“扫描”视图。

## 视图内局部导航

- **回测页（Backtest）**
  - “历史记录”按钮打开回测历史弹窗（modal）
  - “筛选/排序”在表格头部通过 `data-sort-key` 与筛选输入实现
  - “批量参数测试”是回测页内嵌子模块（不单独占用顶栏）
- **策略调试（Debug）**
  - 特征快照区含 tab（core/channel/decision）切换
  - 交易明细表支持点击“查看”展开详情
- **数据（Data）**
  - 同步输出与质量检查输出均为可滚动日志面板

