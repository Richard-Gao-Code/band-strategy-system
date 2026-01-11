# 组件库

本项目未使用组件框架；组件形态由 Tailwind 风格工具类 + 少量自定义 CSS 组合而成。核心复用单位以“样式类 + 结构约定 + DOM id”为主。

## 基础组件

### 1) 导航按钮（Nav Button）

- **主要类**：`.nav-btn`
- **激活态**：`setActiveView()` 会为当前按钮添加 `bg-blue-50 text-blue-600 ...` 等类（见 [app.js](file:///f:/Projects/band-strategy/static_bak/app.js#L2439-L2465)）
- **交互**：点击切换对应 view

### 2) 卡片容器（Glass Card）

- **主要类**：`.glass-card`（在 HTML 中大量使用）
- **用途**：模块分区、承载表单/表格/日志/图表
- **视觉要点**：浅色背景 + 边框 + 圆角 + 间距；暗色模式下替换背景/边框颜色

### 3) 按钮（Button）

- **主按钮**：`.btn-primary`
  - 用途：开始扫描、开始回测、应用预设、保存等关键动作
- **次按钮**：`.btn-secondary`
  - 用途：取消/清空/导出/打开弹窗等次级动作
- **危险动作**：通常使用 `text-rose-*` + `border-rose-*` 或 `bg-rose-500/10` 组合（例如“清空全部”）

示例：

```html
<button class="btn-primary px-4 py-1.5">开始扫描</button>
<button class="btn-secondary px-4 py-1.5">清空</button>
```

### 4) 表单输入（Input / Select / Textarea）

- **统一基类**：`.form-input`（HTML 中大量使用）
- **焦点态**：边框变主色，阴影弱高亮（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L100-L132)）
- **尺寸策略**：通过 `text-[10px]/text-xs` 与 `py-*` 细粒度调节

### 5) 开关与勾选（Checkbox / Radio）

- 常用类：`form-checkbox`、`form-radio`
- 用途：启用指数、实时、稳健分段、质量检查选项等

### 6) 表格（Table）

通用结构：

- `thead` 固定：`sticky top-0` + `backdrop-blur-sm`
- `th` 支持排序：`data-sort-key="..."` + 鼠标悬停变色
- `tbody`：通过 JS 动态渲染行

### 7) 进度条（Progress）

- 外层：圆角灰底条
- 内层：蓝色或渐变色 div，通过 `style="width: xx%"` 动态更新

### 8) 日志面板（Log Panel）

- 固定高度可滚动区域
- 通过 `appendRunLog()` 等方式追加文本（模块：扫描/回测/同步/质量检查等）

### 9) 弹窗（Modal）

- 结构：全屏遮罩 + 居中面板
- 关闭：点击遮罩或“关闭”按钮
- 典型弹窗：回测历史、回测详情、批量参数测试结果等（见 `bt-history-modal`、`bt-detail-modal`、`pt-modal`）

## 业务组件（按模块）

### 扫描（Scan）

- 扫描配置表单：数据目录、股票代码、指数文件/代码、实时开关
- 扫描任务控制：开始扫描 / 中断（`scan-btn` / `scan-cancel-btn`）
- 扫描结果表格：`#scan-results` 动态渲染

### 配置（Config）

- 预设选择器：`#preset-select` + 保存/应用/删除
- 参数编辑器：大量 `cfg-*` 输入框
- 参数说明面板：点击输入框后，右侧/下方展示参数解释（来源：`PARAM_DEFINITIONS`）

### 回测（Backtest）

- 回测配置表单：目录/指数/日期区间/稳健分析开关
- 结果表格：支持排序、筛选、导出
- 详情侧栏（或弹窗）：交易明细、参数分组、拒绝原因等
- 批量参数测试子模块：标的列表 + 参数组合 + 网格生成 + 任务列表

### 池子（Pool）

- 池子 CRUD：股票代码、预警价、备注；本地保存
- 池子操作：用池子扫描、用池子回测、星池监控

### 日记（Journal）

- 表单字段：日期、股票代码、方向、是否按策略、原因、依据、心理活动等
- 操作按钮：保存、清空表单、清空全部

### 数据（Data）与任务（Tasks）

- 数据文件列表：从后端读取目录文件列表
- 数据同步：一次性同步（流式输出）
- 质量检查：对目录/标的做质量检查（流式输出）
- 定时更新：启动/停止任务 + 任务状态概览

### 选股决策（Selector）

- 一键运行：开始选股
- 结果区域：表格/列表 + 关键指标展示

### 策略调试（Debug）

- 输入：标的、数据文件/目录、日期区间、策略参数
- 输出：overview、交易明细、特征快照（按 tab 展示）

