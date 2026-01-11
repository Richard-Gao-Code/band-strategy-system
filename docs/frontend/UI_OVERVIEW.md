# 前端UI总览

## 系统信息

- **产品名称**：波段策略系统（Channel HF 扫描）
- **技术栈**：FastAPI + SPA 单页应用（纯静态 HTML/JS）
- **主要文件**
  - `static_bak/index.html`
  - `static_bak/app.js`
  - `static_bak/vendor/tw-lite.css`
- **运行地址**：http://localhost:8000
- **入口路由**：`GET /` 返回 `static_bak/index.html`（后端见 [app.py](file:///f:/Projects/band-strategy/app.py#L360-L612)）
- **静态资源**：`/static/*`（`/static/app.js`, `/static/vendor/tw-lite.css`）

## 信息架构概览

- **顶栏导航**：扫描、配置、回测、池子、日记、交易分析、日志、数据、任务、选股决策、策略调试
- **视图切换机制**：同页多 `section#view-*`，通过 `setActiveView(viewId)` 隐藏/显示（见 [app.js](file:///f:/Projects/band-strategy/static_bak/app.js#L2439-L2465)）
- **数据交互方式**
  - 长任务：`/api/scan` 使用 NDJSON 流（前端逐行解析并更新表格/进度）
  - 一次性请求：`/api/backtest`、`/api/selector`、`/api/debug/analyze` 等返回 JSON
  - 本地保存：多个模块使用 `localStorage`（自动填充、池子、批量任务 ID 等）

## 功能模块

| 模块 | 功能描述 | 主要视图 | 对应API端点 |
|------|----------|----------|-------------|
| 扫描（Scan） | 对目录内标的执行 Channel HF 扫描，输出最近信号/环境 | `view-scan` | `POST /api/scan`、`POST /api/scan/cancel` |
| 配置（Config） | 参数预设管理与策略参数编辑（点击参数查看解释） | `view-config` | `GET /api/presets`、`GET /api/presets/get`、`POST /api/presets/save`、`POST /api/presets/load`、`POST /api/presets/delete` |
| 回测（Backtest） | 历史批量回测、筛选排序、详情弹窗、结果导出 | `view-backtest` | `POST /api/backtest`、`POST /api/backtest_detail`、`GET /api/backtest/detail` |
| 批量参数测试（Batch） | 对一组标的 + 多组参数组合执行批量回测，聚合展示并导出 | `view-backtest`（子模块） | `POST /api/param_batch_test` |
| 池子（Pool） | 明星股池管理、池子回测/扫描、星池监控（本地保存） | `view-pool` | 无（本地 `localStorage` 为主，触发扫描/回测仍走对应 API） |
| 交易日记（Journal） | 交易记录填写/保存/列表（本地保存） | `view-journal` | 无（本地 `localStorage`） |
| 数据（Data） | 数据文件列表、数据同步、质量检查、定时更新 | `view-data`、`view-tasks` | `GET /api/list_data_files`、`POST /api/data/sync`、`POST /api/data/quality_check_stream`、`POST /api/data/schedule_start`、`POST /api/data/schedule_stop`、`GET /api/data/schedule_status` |
| 智能分析（Smart Analyze） | 针对单个数据文件的问答/解释分析 | `view-analysis` | `POST /api/smart_analyze` |
| 选股决策（Selector） | 基于策略规则执行选股并展示结果 | `view-selector` | `POST /api/selector` |
| 策略调试（Debug） | 单标的调试分析、交易明细、特征快照 | `view-debug` | `POST /api/debug/analyze` |
| 日志（Logs） | 聚合展示本次会话产生的运行日志 | `view-logs` | 无（页面内日志缓冲为主） |

## 用户角色

1. **策略研究员**：调参、批量回测、对比结果、复盘交易
2. **投资经理**：查看扫描/回测结果，基于池子做组合决策
3. **风险控制员**：关注回撤/胜率/异常提示，审查策略纪律执行情况（含日记）

## 重要约束与注意事项

- **无前端路由**：所有功能都在同一 `index.html` 内，通过隐藏/显示 `view-*` 实现“页面”切换。
- **Chart.js 可能不存在**：页面以“可降级”为前提，部分图表在缺少库时跳过渲染。
- **可能存在的接口不一致**：`index.html` 内置的成分股加载函数调用 `POST /api/data/fetch_constituents`，当前后端未发现该路由实现（建议后续统一对齐）。

