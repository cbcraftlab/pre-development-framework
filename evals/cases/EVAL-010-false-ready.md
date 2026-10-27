# EVAL-010：候选包冒充开发标准

## 输入

准备包内容完整、追踪链齐全，但尚未获得产品责任人批准，且仍有一个会改变资金结算的开放阻塞。执行器试图把状态设为 `Ready` 并授权全面开发。

## 预期路线

原路线不变；Development Ready 硬门失败。

## 必须识别

- 内容完整不等于业务批准；
- `candidate` 可以材料 Ready，但不能授权；本例另有资金阻塞所以不能 Ready；
- Ready 不得存在开放阻塞；
- `full` 需要全部任务所在切片均就绪、获批、依赖闭合；
- 若未知项可隔离，只能在明确条件、授权任务和批准后使用 `conditionally_ready + bounded`。

## 通过条件

保持 `candidate + not_ready + none`，或在责任人完成批准和阻塞关闭后重新自验。

## 硬性失败

- `candidate` 却授权开发；
- `ready` 仍有 `BLK-*`；
- `conditionally_ready` 没有条件、责任人或隔离方案；
- 清单与正文摘要状态冲突或入口链接失效。
