# 从需求到开发准备包

## 1. 环境与输入

需要 Git、Python 3.9+；无需第三方包、云端服务或密钥。`python3 --version` 核对版本；Windows 可使用 `py -3`。在仓库根目录运行 `python3 -B scripts/check_all.py`。这是框架自身检查，不会修改真实项目，也不证明需求已经正确。

准备：用户明确指定且实际存在的项目/文档根目录、需求原文/PRD、可读取的现状证据，以及本次团队职责。没有代码的新产品也可以有文档根目录。不要在输入中填写密码、令牌或客户原始数据。

## 2. 最短路径：轻量新需求

用编辑器把 `templates/quick-input.json` 复制到目标项目，命名为 `predev-input.json`。填写项目/包标识、标题、目标、范围、非目标、可观察验收及验证方式。示例文案不是自己的产品决定。

`team`、`owner` 可以留空。提供人员时使用 `templates/00-project-context.json` 的成员字段；`confirmed_responsibilities` 只能填写用户已确认职责。一个人可以兼任多种角色，这仍不等于批准需求包。

在框架根目录执行，替换两个绝对路径：

```text
python3 -B scripts/new_package.py --project-root "/absolute/path/to/project" --brief "/absolute/path/to/project/predev-input.json" --dry-run
python3 -B scripts/new_package.py --project-root "/absolute/path/to/project" --brief "/absolute/path/to/project/predev-input.json"
```

预期 `DRAFT CREATED` 和 `candidate + not_assessed + none`。初始化器仅处理 `new + light`：创建新包并向 `docs/pre-development/index.md` 追加导航，不覆盖已有包，不改根 README，不授予开发权限。输入原文快照和 SHA-256 一起登记为来源。

| 文件 | 用途 |
| --- | --- |
| package-manifest.json | 身份、来源、状态、授权与导航 |
| project-context.json | 团队与约束；缺失项保持未知 |
| delivery-plan.json | 需求、验收、任务、切片和依赖 |
| development-ready.md | 草稿、待完成核对与语义解释 |
| development-ready.html | 派生阅读版，浏览器直接打开 |
| input-brief.json | 原始输入快照，不冒充最新批准 |

结构化内容自动生成以减少填写。需要产品判断的内容仍由人或助手核对，不能靠初始化器直接设为 Ready。

## 3. 从草稿到材料就绪

按 [路线](../routing/route-selection.md) 复核风险，再读取适用协议。文案调整不强制生成架构或数据模型；资金、权限、新事务模型等变化升级受影响范围。轻量包只解释适用结论，不复制完整路线空表。

核对来源、实现位置、目标和非目标、异常、主责及验收。资料冲突形成问题，模型不静默选择。收到责任人回答后，登记来源并回写全部受影响 ID。

在 delivery-plan 中给每项验收分配任务。涉及已就绪切片的需求，其剩余验收也必须有任务归属；可以分配到受阻切片，不要求无关工作一起就绪。需求过大时按独立可验收结果拆分。

完成适用自验后逐个更新切片就绪度，再更新清单总结。正文 `predev-meta` 与清单六项元数据同步；Markdown 解释规则，JSON 保存任务映射。完整路线还需未参与起草者隔离复读，不能制造独立复核证据。

无阻塞候选材料可以为 `candidate + ready + none`，表示材料可以评审，尚未获准开发。

## 4. 重建阅读版与校验

修改清单、正文、计划、上下文或登记图后，重新生成 HTML：

```text
python3 -B scripts/render_readable_package.py --source "/absolute/path/to/project/docs/pre-development/REQ-001-local-export/development-ready.md" --output "/absolute/path/to/project/docs/pre-development/REQ-001-local-export/development-ready.html"
python3 -B scripts/validate_project_package.py --project-root "/absolute/path/to/project" --package-dir "docs/pre-development/REQ-001-local-export"
```

预期 `VALIDATION PASSED`，只代表实现覆盖的结构、引用、授权登记和派生检查。再实际打开 HTML 核对表格、图、目录和文字。自定义阅读标题在清单登记 `readable_title`，不手工编辑 HTML。

复杂图登记源码与本地 SVG/PNG 等。渲染器展示已有图片，**不把 Mermaid 自动转换为 SVG**；使用自己的绘图工具导出并核对。无需为阅读安装编辑器插件。

## 5. 批准与授权

由有权决定范围、契约和验收的人评审精确包版本。得到真实批准记录后，才给切片填写 approval：批准人、ISO 时间、可追溯位置及 approved_package_version。合成示例不提供真实批准。

确认材料就绪、条件可隔离且依赖都在授权范围后，登记 authorized=true；清单 authorized_work 必须恰好等于授权切片任务集合。bounded 表示部分任务；full 表示本包全部任务，不是产品上线许可。高后果未决条件禁止授权相关切片。

有无关阻塞时允许 `approved + not_ready + bounded`，只授权独立且获批的就绪切片。授权之后仍需重建阅读版、校验，框架到此停止。

## 6. 存量、变更与完整路线

初始化器不猜历史。存量新增使用 enhancement，已有需求变更使用 delta。参照 [标准样例](../examples/synthetic-project/docs/pre-development/REQ-002-sample/development-ready.md) 和 [增量样例](../examples/synthetic-project/docs/pre-development/REQ-003-sample/development-ready.md)，从模板建立新包；baseline_refs 明确版本、定位和复用条目，delta 同时登记 changes。保留原包，不覆盖旧批准。

复杂需求参考 [完整路线示意](../examples/synthetic-project/docs/pre-development/REQ-004-web-server/development-ready.md)：仅以虚构 Web 端和服务器展示边界、契约引用、状态、图和阻塞。不提供真实业务流程；因此该包明确保持 not_ready，不能照抄为可开发产品需求。

语义、职责或授权改变时升包版本，复核受影响切片并更新批准引用；复用未失效证据。支持范围见 [兼容政策](compatibility.md)。

## 7. 常见问题

| 现象 | 处理 |
| --- | --- |
| project root 错误 | 指定实际存在的绝对目录，先确认目标 |
| package already exists | 核对旧包，独立新需求用新 ID/slug，不覆盖 |
| unknown reference / responsibility | 修正 ID，填写真实确认职责；未知项维持未就绪 |
| acceptance coverage incomplete | 给遗漏验收分配任务，或重新拆分独立范围 |
| HTML stale / differs | 从事实源重建完整 HTML，不删除标记绕过检查 |
| diagram not rendered | 核对图片文件、登记和 HTML 输出；代码块不是可见图 |
| unsupported framework_version | 显式迁移，不只替换版本号 |

I/O 错误可能保留未完成草稿；按错误核对新包和索引再恢复，不自动删除已有资料。
