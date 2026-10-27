# 结构化交付契约（0.10）

## 最小文件与事实归属

使用模板创建包后，先填真实项目资料，再判定就绪。空白模板通过 JSON 结构检查，不等于可以交付或开工。

| 文件 | 权威内容 | 正文如何使用 |
| --- | --- | --- |
| package-manifest.json | 包身份、模式、风险路线、来源、全包结论、授权任务与文件导航 | 摘要与 predev-meta 标记同步清单 |
| project-context.json | 本次项目约束、成员、已确认职责、可用时间及分工建议 | 解释能力缺口和取舍，不另存一套分工 |
| delivery-plan.json | 需求、验收、契约引用、任务、切片与变化映射 | 引用稳定 ID，解释规则与拆分理由 |
| development-ready.md | 产品语义、范围、异常、适用系统视图、决策和复核证据 | 位于包根目录，可按复杂度拆附件 |
| development-ready.html | 由正文和结构化计划派生的阅读版 | 不单独编辑；附带 JSON 映射表 |

`07-development-task.json` 用于分析时展开任务卡；最终将执行所需引用与负责人归入 delivery-plan，不同时维护两套生效任务记录。更多上下文通过任务 scope/objective 或正文 ID 段落表达，业务规则无需复制进每张卡。

## 交付计划字段

- requirements：`id / statement / source_ids / acceptance_ids`。记录本包范围内需要实现的行为，排除的愿望写非目标。
- acceptance：`id / criterion / method`。明确输入或前置条件、动作、可观察结果与验证方式；不能只写“正常”。
- contracts：`id / owner / state / definition / evidence`。definition 可为精确契约正文位置或定义；evidence 为已核对版本或确认记录。空集表示本任务无需跨边界契约，不表示可忽略实际存在的接口。
- tasks：`id / title / objective / scope / non_goals / requirements / acceptance_ids / contracts / depends_on / owner / responsibility / collaborators / slice_id`。依赖引用本包任务；既有已完成能力引用 baseline_refs 与契约证据，不伪造本包待执行任务。对尚未交付的外包依赖，记录阻塞或受控前置切片，不能当已完成基线。
- slices：`id / task_ids / readiness / blockers / conditions / authorized / integration_owner / acceptance_owner`。可选 approval 记录批准人、时间、位置和当前包版本。一个人可以兼任实施、联调和验收；人员缺口可暂留空并保持未就绪。
- changes：`kind / id / before / after / affected_tasks`。delta 必填，其他模式按需。删除条目引用旧 ID；新增、修改、保留条目引用当前计划 ID。被删除需求必须有删除后结果和影响解释，不能机械地把旧任务也保留为授权任务。

稳定 ID 在当前计划内唯一。变更不复用旧 ID 表示无关新业务。材料 ready 要求任务主责的 responsibility 属于该成员 confirmed_responsibilities；建议不会自动转为已确认职责。

条件项需有 owner、ISO 日期 decision_by、isolation、invalidated_tasks 与 high_consequence。授权切片的依赖须同时位于授权范围。批准记录锁定 approved_package_version；包版本改变后复核影响并更新证据，不复制旧批准时间冒充新批准。

## 来源与引用

清单 sources 记录 normative（期望或已确认规则）与 observed（代码、接口、运行或其他现状证据）。authoritative/supporting/excluded 是另一维度，角色互斥，已登记来源都有角色。两者独立：一份权威 PRD 不能证明接口已存在。每条需求至少引用一个权威规范性来源来支持期望行为；代码观察可以补现状证据，不能单独决定产品应该怎样。

`checked_at`、`approved_at`、`decision_by` 使用 ISO 日期或日期时间。时间格式可机械检查；真实性、时效性和期限是否足够由复核判断。外部资料用精确 URL、文档版本或记录 ID，本地证据优先使用以包目录为基准、指向项目内文档的相对路径；证据定位不作为输出写入路径。

enhancement/delta 使用 baseline_refs 明确引用版本及 reused_items。清单 clarification_closures 记录已关闭问题、答案来源、affected_ids 与 updated_ids。校验器只能检查回写登记包含受影响 ID；回写是否正确、遗漏了哪些影响必须通过语义复核。

## 校验边界

校验器检查格式、必填项、引用、重复 ID、依赖环、任务与切片归属、验收覆盖、已确认职责、契约确认登记、批准版本和授权依赖，以及文件路径、导航、派生产物更新。

它不能证明人员能力、PRD 正确性、接口确实可用、契约内容充分、批准记录真实、条件隔离成立或图业务正确。复杂度是否如实申报也属于语义复核。完整路线正式使用前仍需未参与起草者复读；不得用机器 PASS 替代。

派生指纹包含清单与已登记源文件（排除阅读版自身）。正文、JSON、图或清单改变后都要重建 HTML；包根之外的项目入口不参与指纹，所以新增其他包不会使旧包阅读版无故过期。正文不重复维护 JSON 的任务表；HTML 自动附表供人员阅读。指纹用于漂移检测，不是签名或安全认证。

0.10.0-candidate.2 补充：已就绪切片涉及的每条需求，其全部验收必须有显式任务承接，可以位于其他受阻切片；无关草稿不因此阻塞。每个已就绪任务须对其每条需求至少引用一个对应验收。图必须实际输出为 HTML 图片，代码块里的图片语法不算可见图。阅读版比对整个文档，包含 head、样式和安全策略；可选 readable_title 登记自定义标题。生成器只支持声明的 Markdown 子集，不承诺完整 CommonMark；Mermaid 到图片的导出由选用工具完成。

旧版 0.9.0-candidate.5 仍调用冻结旧规则，不会获得新版新增检查的保证。其他未支持版本明确报错；迁移规则见 [变化与证据](change-and-evidence.md)。
