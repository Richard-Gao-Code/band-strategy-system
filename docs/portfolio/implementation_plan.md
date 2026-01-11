# E阶段任务1：投资组合优化核心算法原型（实施计划）

## 目标
- 第一阶段先实现“无外部依赖”的最小可用原型，确保系统在缺少 PyPortfolioOpt 时也能工作
- 第二阶段再集成 PyPortfolioOpt 作为增强优化引擎
- 输入：多个策略的历史收益序列
- 输出：最优权重分配与核心风险指标

## 模块产出
- `core/portfolio/portfolio_optimizer.py`
  - 等权重（基准方法）
  - 逆波动率加权（回退方案）
  - 最小方差优化（基础均值-方差逻辑，使用 `returns.cov()`）
  - 预留 PyPortfolioOpt 引擎接口（可选）
- `tests/test_portfolio_optimizer.py`
  - 权重和为 1 的基本约束验证
  - 异常输入处理与边界场景验证

## 依赖与安装
- 第一阶段：仅依赖 numpy/pandas（项目已使用）
- 第二阶段（可选）：PyPortfolioOpt：`pip install PyPortfolioOpt`
- Windows 环境可能需要 C++ 构建工具链（如 Visual Studio Build Tools）；若 cvxpy/cvxopt 安装失败，保持基础引擎可用并以其作为回退路径

## 下一步（E阶段后续任务衔接）
- 接入现有数据库：将策略历史绩效转换为收益矩阵（策略 x 时间）
- 增加约束与风控：权重上下限、策略分组约束、目标波动/最大回撤等
- 输出再平衡建议：与现有 API/任务编排系统集成，支持异步计算与结果落库
