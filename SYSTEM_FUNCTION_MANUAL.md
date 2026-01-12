# band-strategy 系统用户手册（详细功能说明）

本系统为单体应用：FastAPI 后端 + 纯静态 SPA 前端 + 回测/扫描引擎。主要面向“策略研究 / 扫描选股 / 回测复盘 / 参数优化 / 组合权重优化 / 数据维护”等日常工作流。

## 1. 快速开始

### 1.1 启动方式

- 启动 Web 服务：`python app.py`
- 默认监听：`http://127.0.0.1:18002/`（可通过环境变量 `CHHF_HOST`、`CHHF_PORT` 覆盖）
- 浏览器打开后，即可使用顶栏导航进入各模块
- 可选能力（智能问数）：需配置环境变量 `DASHSCOPE_API_KEY` 并重启服务

### 1.2 数据准备

- 数据目录需要包含按“标的代码”为文件名的 CSV（例如：`000001.SZ.csv`）
- 扫描/回测会从你填写的目录中自动发现 `*.csv` 文件
- 如需指数确认/对照，可提供指数 CSV 文件路径（可选）

## 2. 顶栏导航与模块概览

前端为单页应用，同一页面通过切换 `view-*` 显示不同模块。常见模块：

- 扫描：对目录内标的执行策略扫描，输出最近信号/环境信息
- 配置：参数编辑与预设管理
- 回测：对目录内标的批量回测并输出绩效指标
- 批量测试：多标的 × 多参数组合的批量回测与汇总对比
- 任务：查看批量任务状态、取消任务
- 选股决策：读取选股输入文件并按阈值筛选输出
- 策略调试：单标的调试分析与复盘解释
- 数据：数据同步、质量检查、备份、定时任务
- 交易特征：交易特征文件管理、导出与重新分析
- 智能问数：对 CSV/Excel 进行自然语言问答分析
- 池子/日记/日志：用于记录与辅助决策（部分数据以本地浏览器存储为主）

## 2.1 系统文件与存储位置约定

- 当前运行配置：项目根目录 [config.json](file:///f:/Projects/band-strategy/config.json)
- 预设保存位置：`presets/*.json`（内置预设“默认/保守/激进”无需落盘文件也可直接加载）
- 当前激活预设：`presets/.active_preset`（存储预设名称）
- 交易特征快照：默认保存在 `exports/trade_features.json`，并支持导出 CSV
- 股票数据：通常为你指定的数据目录下的 `*.csv`（例如项目根目录 [data/](file:///f:/Projects/band-strategy/data)）

## 3. 扫描（Scan）

### 3.1 功能概述
扫描用于快速检查一批标的在“最近交易日”的策略环境与信号，适合每天收盘后批量跑一遍，得到候选池与观察列表。

### 3.2 界面入口
顶栏选择“扫描”。

### 3.3 使用说明

1. 填写“股票文件目录地址”（例如 `data`）
2. 可选填写“股票代码”过滤（逗号/空格/换行分隔）
3. 可选填写“指数数据文件”用于指数确认
4. 点击“开始扫描”

### 3.4 后端接口

- `POST /api/scan`：NDJSON 流式返回
  - 关键字段（逐行）：`start/heartbeat/result/error/end`
  - `start` 会包含 `job_id`，用于取消
- `result.data.env`：用于前端表格展示的“环境快照”
  - 即使当日无买卖信号，`env` 也会返回默认结构（避免出现大量空结果）
- `POST /api/scan/cancel`：请求取消
  - 请求：`{"job_id":"..."}`
  - 响应：`{"ok": true, "msg": "已请求中断"}`

## 4. 回测（Backtest）

### 4.1 功能概述
回测用于在历史区间内执行策略逻辑，输出交易列表与绩效指标，支持批量对比与拒绝原因复盘。

### 4.2 界面入口
顶栏选择“回测”。

### 4.3 使用说明（批量回测）

1. 填写“股票文件目录地址”
2. 可选填写股票代码过滤
3. 可选填写指数数据文件
4. 点击“开始回测”，结果将以流式方式逐行追加到表格

### 4.4 后端接口

- `POST /api/backtest`：NDJSON 流式返回
  - 关键字段（逐行）：`start/heartbeat/result/error/end`

### 4.5 回测明细与拒绝原因

当你需要对单只股票做“交易明细 / 无交易原因 / 过滤链路”复盘时，使用明细接口：

- `POST /api/backtest_detail`：执行单标的明细回测（JSON 返回）
- `GET /api/backtest/detail`：读取单标的明细（用于前端“查看详情”弹窗）

## 5. 配置与预设（Config & Presets）

### 5.1 功能概述
用于统一管理策略参数，支持“保存为预设 / 加载预设 / 删除预设 / 设置当前激活预设”，方便在不同风格（保守/激进）间切换。

### 5.2 界面入口
顶栏选择“配置”。

### 5.3 后端接口

- `GET /api/presets`：列出预设与当前激活项
- `GET /api/presets/get?name=...`：读取某个预设
- `POST /api/config/save`：保存当前配置到 `config.json`
- `POST /api/presets/save`：保存预设文件
- `POST /api/presets/load`：加载预设并设为激活
- `POST /api/presets/delete`：删除预设

### 5.4 内置预设与隔离规则

- 内置预设：默认 / 保守 / 激进
- 预设的保存、加载、应用彼此独立：在“配置”页修改参数不会隐式改写其他预设文件
- “应用预设”会将该预设写入 `config.json` 并设置为“当前应用”

## 6. 批量参数测试（Batch Parameter Test）

### 6.1 功能概述
批量参数测试用于解决手动调参效率低的问题：对多只股票、多个参数组合并行回测，自动汇总并对比结果，支持导出与任务追踪/取消。

### 6.2 界面入口
顶栏选择“批量测试”。

### 6.3 使用说明

#### A. 股票代码输入

- 支持格式：`000001.SZ, 600519.SH`
- 分隔符：逗号、空格或换行

#### B. 参数组合配置（两种方式）

模式一：网格参数生成（推荐）

```
vol_shrink_min: [1.0, 1.05]
vol_shrink_max: [1.1, 1.15]
min_channel_height: [0.04, 0.05]
```

模式二：手动输入组合列表（每行一个组合）

```
vol_shrink_min=1.0, vol_shrink_max=1.1
vol_shrink_min=1.05, vol_shrink_max=1.15
```

#### C. 执行与结果

1. 点击“开始批量测试”
2. 系统将创建一个批量任务 `task_id` 并实时推送结果
3. 表格会展示每个组合的主要指标（例如交易数、胜率、总收益、最大回撤等）
4. 支持导出结果用于二次分析

### 6.4 后端接口

- `POST /api/param_batch_test`：NDJSON 流式返回（包含 `task_id` 与 `grid_metadata`）
- `GET /batch_test/status?task_id=...`：查询任务状态/进度/聚合统计
- `POST /batch_test/cancel`：取消任务
  - 请求：`{"task_id":"..."}`
  - 响应：`{"status":"cancel_requested"}`

## 7. 参数优化（Optimization）

### 7.1 功能概述
参数优化用于在给定参数空间与迭代次数下，自动搜索更优参数组合，并将历史记录落库，便于回溯对比。

### 7.2 后端接口

- `POST /api/optimize/run`
  - 请求示例：
    ```json
    {
      "optimizer_type": "random",
      "strategy_name": "channel_hf",
      "param_space": {
        "vol_shrink_min": [0.98, 1.10],
        "min_channel_height": [0.04, 0.08]
      },
      "n_iterations": 30
    }
    ```
- `GET /api/optimize/history?strategy_name=...&limit=20`：查看优化历史

### 7.3 绩效与记录（Performance）

系统会将部分优化/回测相关指标记录到数据库，便于“最佳参数/历史曲线/统计摘要”的查询展示：

- `GET /api/performance/best/{strategy_name}`：查询某策略的最佳记录
- `GET /api/performance/history/{strategy_name}`：查询某策略历史记录
- `GET /api/performance/stats/{strategy_name}`：查询某策略聚合统计

## 8. 投资组合优化（Portfolio Optimization）

### 8.1 功能概述
投资组合优化用于基于多个“策略收益序列”，计算最优策略权重与风险指标，输出可用于组合分配或再平衡的权重建议。

### 8.2 后端接口

- `POST /api/portfolio/optimize`
  - 请求示例：
    ```json
    {
      "strategy_performances": [
        { "strategy_id": "strat1", "returns": [0.01, 0.02, 0.03] },
        { "strategy_id": "strat2", "returns": [0.02, 0.01, -0.01] }
      ],
      "optimization_method": "min_variance",
      "constraints": {
        "engine": "basic",
        "risk_free_rate": 0.0,
        "frequency": 252,
        "weight_bounds": [0.0, 1.0]
      }
    }
    ```
  - 响应示例：
    ```json
    {
      "success": true,
      "data": {
        "optimal_weights": { "strat1": 0.5, "strat2": 0.5 },
        "risk_metrics": { "expected_return": 0.0, "expected_risk": 0.0, "sharpe": 0.0 },
        "optimization_stats": { "method": "min_variance", "engine": "basic", "n_strategies": 2, "n_observations": 3, "elapsed_ms": 12, "task_id": "..." }
      }
    }
    ```

## 9. 选股决策（Selector）

### 9.1 功能概述
选股决策用于对选股输入文件进行过滤与排序，输出满足条件的候选列表，通常用于从回测汇总结果中筛出更优标的。

### 9.2 后端接口

- `POST /api/selector`
  - 请求字段：
    - `path_ud`：上轨下系文件路径（支持目录，目录时默认文件名 `上轨下系100.csv`）
    - `path_mu`：中轨上系文件路径（支持目录，目录时默认文件名 `中轨上系100.csv`）
    - `max_mdd`：最大回撤阈值（默认 0.10）
    - `min_trd`：最少交易数（默认 15）
    - `calmar_min`：最小 Calmar（默认 3.0）
  - 响应：`{"status":"success","data":...}`

## 10. 策略调试（Debug Analyze）

### 10.1 功能概述
策略调试用于对单标的做更细粒度的解释与复盘，帮助定位“为何买/为何不买/为何卖/条件如何触发”等问题。

### 10.2 后端接口

- `POST /api/debug/analyze`：返回 overview、交易列表与特征快照等调试信息

### 10.3 生效参数面板（可跳转与标记）

调试页右侧“生效参数”支持：

- 点击任一参数：自动切换到“配置”页并滚动定位到对应参数输入框
- 标记“最近修改”：基于本地浏览器记录的最近修改参数列表（用于复盘你刚调过哪些参数）
- 标记“默认≠当前”：将当前输入值与系统内置参数定义的默认值对比（用于快速发现偏离默认的参数）

## 11. 交易特征（Trade Features）

### 11.1 功能概述
交易特征用于管理交易特征文件（例如某次分析输出的特征快照），支持列表、读取、导出与重新分析。

### 11.2 后端接口

- `GET /api/trade_features/list`
- `GET /api/trade_features/get`
- `GET /api/trade_features/export_csv`
- `POST /api/trade_features/reanalyze`

## 12. 数据管理（Data）

### 12.1 数据同步

- `POST /api/data/sync`：NDJSON 流式同步（支持按 symbols 或全量）

### 12.2 数据质量检查

- `POST /api/data/quality_check_stream`：NDJSON 流式质量检查（常用于定位缺失/异常行/日期不连续）

### 12.3 池子备份

- `GET /api/data/backup_pool`：导出池子备份数据（如你在前端维护池子，可用于备份/迁移）

### 12.4 定时任务

- `POST /api/data/schedule_start`
- `POST /api/data/schedule_stop`
- `GET /api/data/schedule_status`

## 13. 智能问数（Smart Analyze）

### 13.1 功能概述
对 CSV/Excel 进行自然语言问答分析（例如“按行业汇总收益”“找出最大回撤的组合”等）。该功能依赖外部模型服务，需要配置 API Key。

### 13.2 使用方式

- `GET /api/list_data_files`：列出可供分析的数据文件（来自 `test/`、`analyze/`、`exports/`）
- `POST /api/smart_analyze`
  - 需要环境变量 `DASHSCOPE_API_KEY`
  - 只支持 `.csv/.xls/.xlsx`

## 14. 参数说明体系（Parameter Definitions）

### 14.1 功能概述
系统提供标准化的参数定义、逻辑解释与调参建议，降低参数含义模糊造成的误用风险。

在“配置”页点击任意参数输入框，会在页面下方显示该参数的详细说明；若该参数未内置定义，会显示“暂无内置说明”。

### 14.2 标准化格式

- 名称：中文名称与变量名
- 类型：数值/布尔/枚举
- 默认值与范围：推荐区间
- 单位：百分比/天数/比率等
- 说明：核心作用与判断逻辑（包含必要公式）
- 示例：典型数值含义
- 优化建议：调大/调小对结果的预期影响

### 14.3 关键参数速查

- `vol_shrink_min / vol_shrink_max`：控制缩量比例范围
- `min_channel_height`：通道最小高度阈值（过滤低波动标的）
- `close_in_channel_min / close_in_channel_max`：收盘价在通道内相对位置（控制买点深浅）

## 15. 常见问题（FAQ）

**Q：端口启动失败或提示占用？**  
A：修改环境变量 `CHHF_PORT`，或关闭占用端口的进程后重试。

**Q：提示“无效的股票目录地址 / 目录下未找到任何CSV数据文件”？**  
A：确认目录路径可访问，且目录内存在 `*.csv` 文件（文件名通常为 `000001.SZ.csv` 形式）。

**Q：批量测试时浏览器卡顿怎么办？**  
A：大量流式结果渲染会影响前端。建议减少一次性组合数，分批运行。

**Q：为什么有些拒绝记录没有“实际值”？**  
A：布尔类过滤（如“是否停牌”）可能没有数值对比，实际值会显示为 `-` 或状态描述。

**Q：导出的 CSV 打开是乱码？**  
A：优先用 UTF-8 打开；在 Excel 中建议“数据→导入文本”并选择 UTF-8（必要时尝试 UTF-8-SIG/GBK）。

**Q：智能问数提示未配置 DASHSCOPE_API_KEY？**  
A：为运行环境设置 `DASHSCOPE_API_KEY` 后重启服务再试。
