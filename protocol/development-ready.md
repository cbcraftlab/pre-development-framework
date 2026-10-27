# Development Ready 质量门

## 独立判断

材料就绪、责任人批准、任务授权、实现验证是不同事实。

- `readiness`：ready / conditionally_ready / not_ready / invalid_input / not_assessed。
- `baseline_status`：candidate / approved / superseded。
- `development_scope`：none / bounded / full，必须与切片授权及 `authorized_work` 一致。

允许 `candidate + ready + none`：材料已准备好，尚未批准，不能开工。批准不能替代就绪检查；未批准的切片、依赖未授权的切片和失效基线都不能进入授权范围。

## 切片优先

每个切片记录任务、readiness、阻塞、条件及独立批准证据（批准人、时间、记录位置和 approved_package_version）。批准必须针对当前包版本；变更后重审受影响切片，再更新批准引用。阻塞只影响本切片与依赖它的切片；保留其他切片的可开发性。准备包有未解决阻塞时总体为 `not_ready`，仍可在总体 `approved` 下授权与阻塞隔离且已就绪的切片。

`ready` 切片不得有阻塞或条件；`conditionally_ready` 切片必须有条件、责任人、最迟决策点、隔离理由和假设否定时的影响任务。条件涉及高后果未决业务规则时不得授权。

全包 `ready` 要求所有切片 ready；全包 `conditionally_ready` 要求全部切片至少有条件就绪。`full` 仅表示本包所有任务均已授权，不代表整个产品上线许可。`invalid_input/not_assessed` 不授权任何任务。`superseded` 必须 scope=none。

## 所有路线的质量要求

目标和非目标明确；需求有可观察验收；事实与目标分开；任务依赖和所有权清楚；关键公开契约无需猜测；没有用内部实现细节代替业务结果；未决项具有影响边界。标准路线检查受影响规则和交互，完整路线补适用的通信、事务、失败恢复、安全与质量属性，并由未参与起草者复读。

完整路线遇到复杂关系必须表达其结构，不能只有调用清单；图、通信记录和契约相互一致。格式不替代内容检查。起草者先做结构和语义自验，再提交责任人批准，最后登记可开发范围；无审批证据不得伪填 approved。

## 交付结论

报告包身份/版本、模式/路线、材料就绪度、批准状态、可开发任务、阻塞及隔离范围、验证证据和限制。机器校验通过仅证明实现覆盖的结构关系；不能证明 PRD 正确、合同充分、模型判断可靠或实现已经验收。
