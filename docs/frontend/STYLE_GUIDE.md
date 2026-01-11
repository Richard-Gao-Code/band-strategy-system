# 样式指南

本项目 UI 以 Tailwind 风格工具类为主，叠加少量自定义 CSS 变量与组件类（见 `static_bak/index.html` 的 `<style>`）。

## 1. 主题与颜色系统

### 1.1 CSS 变量（浅色/深色）

来源：`index.html :root` 与 `.dark`（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L11-L33)）。

| 语义 | 变量 | 浅色 | 深色 |
|------|------|------|------|
| 主色 | `--primary` | `#2563eb` | `#3b82f6` |
| 主色悬停 | `--primary-hover` | `#1d4ed8` | `#60a5fa` |
| 页面背景 | `--bg-main` | `#f8fafc` | `#0f172a` |
| 卡片背景 | `--bg-card` | `#ffffff` | `#1e293b` |
| 边框色 | `--border-color` | `#e2e8f0` | `#334155` |
| 主文字 | `--text-main` | `#1e293b` | `#f1f5f9` |
| 次文字 | `--text-muted` | `#64748b` | `#94a3b8` |
| 导航背景 | `--nav-bg` | `#ffffff` | `#1e293b` |
| 表头背景 | `--table-header` | `#f1f5f9` | `#334155` |

### 1.2 状态色（约定）

项目中常见状态色组合：

- **成功/确认**：`emerald-*`
- **警告/提醒**：`amber-*` / `yellow-*`
- **错误/危险操作**：`rose-*` / `red-*`
- **信息/链接**：`blue-*` / `indigo-*`
- **中性文本**：`slate-*`

## 2. 字体与排版

### 2.1 字体

- **默认字体栈**：`Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`
- **基础字号**：`body` 13px（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L35-L44)）
- **表格/标签小字**：常用 `text-[10px]` / `text-xs`
- **代码/数字**：部分字段使用 `font-mono`（在交易明细、ID、日期等处）

### 2.2 文本语气

- 顶栏菜单：短词（扫描/配置/回测…）
- 标题：模块名 + 关键动作（如“历史批量回测（通道高频）”）
- 说明：小字号灰色提示（如“空行会忽略；没写的参数将使用…”）

## 3. 间距与布局

### 3.1 页面宽度与栅格

- 主容器：`max-w-[1600px] mx-auto px-4`
- 主要布局：大量使用 `grid grid-cols-1 md:grid-cols-12 gap-3`
- 常见边距：
  - 模块之间：`space-y-2`
  - 卡片内边距：`p-3`

### 3.2 圆角与阴影

- 卡片圆角：8px（`.glass-card`）
- 输入框圆角：6px（input/select/textarea）
- 阴影：默认轻阴影，hover 提升（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L53-L65)）

## 4. 组件样式规范

### 4.1 按钮

- `.btn-primary`
  - 背景：主色
  - 悬停：主色 hover + 轻微上移
- `.btn-secondary`
  - 透明背景 + 边框
  - 悬停：表头背景色 + 边框加深

### 4.2 表单

- 统一的背景/边框来自 CSS 变量
- focus 态：边框变主色 + 2px 外发光（浅色/深色不同透明度）

### 4.3 表格

- `thead` 置顶：`position: sticky; top: 0`
- 行 hover：浅色使用主色透明背景；深色使用蓝色透明背景（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L66-L85)）

## 5. 动效与反馈

- 视图切换：`fadeIn` 动画（0.3s）应用于当前显示的 `view-*`（见 [index.html](file:///f:/Projects/band-strategy/static_bak/index.html#L140-L147)）
- 交互反馈：
  - hover 变色/阴影提升
  - 关键动作按钮提供 shadow（如“开始扫描”）

## 6. 深色模式

- 通过在 `html` 或 `body` 上切换 `.dark` 类实现主题替换
- `#theme-toggle` 负责触发切换（按钮位于顶栏右侧）

## 7. 可用性与可访问性（现状约定）

- 表单标签普遍为小字 + 大写字距（`uppercase tracking-wider`）
- 表格以密集信息展示为主，字号偏小，适合桌面端使用
- 重要状态以颜色 + 文案同时表达（例如“待开始/运行中/完成”徽标）

## 8. 响应式策略

- 使用 Tailwind 的 `md:` / `lg:` 断点控制栅格列数与布局
- 移动端以单列堆叠为主；桌面端以 12 列栅格对齐

