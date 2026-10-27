# Development Ready 开发准备包

<!-- predev-meta: framework_version=0.10.0-candidate.2; package_id=REQ-001; package_version=0.1.0; baseline_status=candidate; readiness=not_assessed; development_scope=none -->

> 本文件可以合并完整路线的逻辑产物，但不得删去适用结论。清单是机器入口，本文件解释业务规则；delivery-plan.json 是任务、依赖、负责人和验收映射的事实源。
>
> 本 Markdown 是主事实源；交付时使用 `scripts/render_readable_package.py` 生成同目录 HTML 人类阅览版，并把本地可见图登记到清单。

## 0. 包身份、使用边界与结论

记录 project_id、mode、route 及裁剪理由。材料就绪、批准、可开发范围分开。

## 1. 权威输入、辅助输入、排除输入与用户确认

## 2. 问题、目标、范围与参与者

## 3. 需求、规则、对象、状态、流程与验收

## 4. 能力、模块、数据与入口所有权

## 5. 跨模块交互、公开能力与正式契约

### 5.1 通信拓扑与边界原则

```mermaid
flowchart LR
  A["入口/调用方"] -->|"COMM-001"| B["能力提供模块"]
```

### 5.2 `COMM-*` 通信模式目录

### 5.3 事务、一致性、投递与失败恢复

### 5.4 统一请求/消息信封

### 5.5 `INT-*` 公开能力与交互目录

### 5.6 `CON-*` 正式契约与所有权

## 6. 架构约束、质量属性与延迟决策

## 7. 纵向切片、开发任务、团队映射与依赖

引用 delivery-plan.json 中稳定 ID，解释拆分与隔离理由；HTML 自动附带结构化表格。

## 8. 联调、Mock 与验收准备

## 9. 决策、澄清、风险、阻塞与可开发范围

## 10. 需求追踪矩阵（含 `COMM-* / INT-* / CON-*`）

## 11. 自验、隔离复读与基线批准

记录检查结果、责任人、证据位置、尚未验证事项及受影响切片。完整路线正式使用前需要未参与起草者复读；自身重读不能冒充独立复读。
