# 可选 CI/CD 配套

把已完成开发的代码持续验证，并把可追溯的产物交付到运行环境。此目录供开发团队按需复制；不属于 Development Ready 质量门，也不要求框架使用者采用某种语言、云厂商或部署工具。准备包获批不等于获准启用发布。

示例仅描述虚构的 Web 前端＋服务器：前端用 Node.js、服务端用 Go、镜像存入 GHCR、部署到 Kubernetes。其他语言替换检查命令，其他镜像库替换登录/镜像命名，其他运行平台替换部署适配器；核心规则仍适用。

## 流程与默认行为

```text
PR → 检查、测试 → 构建两个镜像，不上传、不部署
main push → 检查、测试 → 构建并上传镜像 → 显式启用后部署 test
手动触发 main → 检查、测试、上传 → 按选择部署 test / production
```

- 检查失败会阻断镜像发布和部署；镜像构建失败会阻断部署。
- 基础版每次验证和构建两个组件，避免遗漏共享依赖、Dockerfile 或工作流修改。确认成本和依赖图后再做增量优化。
- 镜像标记为 `sha-<完整提交>`，实际部署使用 `image@sha256:<digest>`；部署使用同一运行产生的 digest。单凭 SHA 标签不能保证重跑后的字节相同，回滚记录必须保留 digest。
- PR 使用只读权限，不登录镜像库，不读取部署凭据；发布 job 单独获得 packages 写权限。只在 main push 或 main 手动运行时上传镜像。
- 测试自动部署默认关闭。生产部署必须手动选择、输入确认文本，并显式启用 production 环境。环境审批还要在 GitHub 后台配置。
- 同一环境的部署使用同一个 concurrency group，不取消正在执行的部署；其他发布流程也须共用该组。GitHub 并发队列不保证 FIFO，排队运行可能被更新的运行替换。

文件均位于 integrations 下；仅下载本框架不会运行这些模板，也不会改变本仓库已有的框架校验工作流。

## 文件与最短接入路径

| 来源 | 复制到目标项目 |
| --- | --- |
| [project-ci.yml.example](project-ci.yml.example) | `.github/workflows/project-ci.yml` |
| [deploy.py](deploy.py) | `.ci/deploy.py` |
| [发布检查清单](release-checklist.md) | 按项目维护在发布文档中，不必固定路径 |

手动复制前确认目标文件不存在；若已有流水线，先审阅并合并，不直接覆盖。模板没有安装器，不会替你改目标项目或后台设置。

目标项目需要自行提供：

```text
web/package.json          # 定义 test:ci 和 build，测试命令须返回真实失败状态
web/package-lock.json
web/.node-version         # 项目选择的受支持 Node.js 版本
web/Dockerfile            # 构建上下文为 web/
server/go.mod             # Go 版本取自此文件
server/go.sum
server/Dockerfile         # 构建上下文为 server/
.ci/deploy.py
.github/workflows/project-ci.yml
```

`test:ci` 不用 `--if-present` 静默跳过；应按项目补前端测试。Go 的 opt-in、数据库和外部集成用例需要独立准备测试设施，`go test ./...` 不保证这些用例都执行。测试只使用隔离环境和合成数据，不连接共享/生产库。镜像 Dockerfile 的基础镜像、依赖锁定和漏洞处理由目标项目维护。

第一次接入先只启用 CI：确认 PR 只验证，main 上传的两个镜像与提交对应，之后才配置测试部署。GHCR 需允许目标仓库的 GITHUB_TOKEN 写入这两个 package；已有 package 可能还需要授予仓库访问权限。目标集群拉取私有镜像的凭据单独配置，不能把短期 GITHUB_TOKEN 当长期拉取凭据。

## GitHub 一次性设置

1. 保留目标分支为 `main`，或同步修改触发器、手动运行检查和部署分支限制。设置保护规则/Ruleset，将 `Project CI / Checks` 作为必需检查；以实际 Actions 检查名称为准。PR 不做路径过滤，以免文档 PR 的必需检查永远等待。
2. 在 Settings → Environments 预先创建 `test` 和 `production`，都限制只允许 `main` 部署。
3. production 配置 required reviewers、阻止自批，并按组织政策限制管理员绕过。**仅写 `environment: production` 不会创建审批规则。** GitHub 套餐和仓库可见性可能限制审批能力；无法满足项目审批要求时保持生产部署关闭，采用经过评审的外部批准流程或适用方案，不能把手动触发等同独立审批。
4. 在两个 Environment 内分别配置下表变量和 Secret；凭据按环境隔离，限制到目标命名空间和必要资源。不要把 kubeconfig、令牌或业务密码提交到代码、构建参数、日志或本目录。
5. 仓库 Actions Variable `ENABLE_TEST_DEPLOY` 默认不设置，验收测试部署后才设为字符串 `true`。production 的 Environment Variable `ENABLE_PRODUCTION_DEPLOY` 也默认不设置，完成审批、迁移及回滚准备后才设 `true`。配置这些开关需项目所有者授权。

| Environment 配置 | 用途 |
| --- | --- |
| Secret `KUBE_CONFIG_B64` | 当前环境受信任、最小权限 kubeconfig 的 Base64；Base64 不是加密 |
| Variable `KUBECTL_VERSION` | 按集群兼容范围选择精确版本，例如 `vX.Y.Z`，不可直接填示例 |
| Variable `KUBE_NAMESPACE` | 已存在的目标命名空间 |
| Variables `WEB_DEPLOYMENT` / `SERVER_DEPLOYMENT` | 已存在的两个 Deployment 名称 |
| Variables `WEB_CONTAINER` / `SERVER_CONTAINER` | Deployment 内要更新的容器名称 |
| Variable `SMOKE_URL` | 无认证信息、无查询参数的 HTTPS 健康检查地址 |

适配器只更新镜像并等待滚动完成，不创建集群、Namespace、Deployment、拉取凭据或应用配置。先完成这些设施及对应探针设置。若 GitHub runner 无法访问集群，按组织网络策略选择受控 runner 或网络接入；不直接照抄任何公司的公网配置。

## 验证、迁移与回滚

在目标项目设置上表非秘密变量及虚构 digest 后，可先运行 `python3 .ci/deploy.py`，默认只输出计划，不调用 kubectl/curl，也不需要 kubeconfig。真实发布使用 `--execute`，才会读取 kubeconfig、更新镜像、等待滚动和检查 HTTPS 健康端点。生产还要求环境开关及本次确认文本。默认 dry-run 是本地规划工具，不检查真实镜像、集群、网络或审批状态。

上线前按 [发布检查清单](release-checklist.md) 验证以下边界：

- **迁移**：模板不执行也不检测数据库迁移。含 schema 变化的提交，在 push main 前关闭测试自动部署，先完成兼容迁移和审阅，再手动部署；生产遵循自身迁移审批。稳定项目可增加经过测试的迁移 job，不能只加一个“已完成”字符串冒充执行证据。
- **部分失败**：两个 Deployment 并非原子更新。一个完成、另一个失败时流水线报错，但已更新组件不会自动恢复；先核对实际状态、兼容性与任务影响，再决定继续发布或按旧 digest 回滚。
- **回滚**：在 Actions 镜像 job 摘要保存提交与两个 digest；发布前另行保存当前运行的两个旧 digest。按同样审批和环境串行规则，用旧 digest 更新两个 Deployment、等待 rollout 并重做健康与业务验收。不要依赖可移动的 latest、重新构建旧提交或未经核对的 ReplicaSet 历史。
- **探针与业务**：kubectl rollout 和 HTTPS 2xx 只证明相应基础状态，不代表登录、关键业务、资金、数据迁移或真实用户体验已通过。

## 增量构建与日常维护

需要优化时，先明确每个镜像的构建上下文和共享依赖。测试至少覆盖：只改 Web、只改 Server、共享库/锁文件、Dockerfile、工作流、部署脚本、删除/重命名以及无法取得比较基线。未知范围回退全量构建；未重建组件复用已经发布并验证的 digest，禁止随手读 latest 拼出一个版本。新增矩阵组件时同步检查部署映射和回滚记录。

Action 固定到完整提交，本次从官方仓库解析于 2026-10-27；注释记录版本。更新时核对官方发布、运行环境要求和新 SHA，重新 lint 并在目标项目试跑。kubectl、Go/Node 和基础镜像版本随项目维护，框架不统一替项目升级。

框架维护者运行 `python3 -B scripts/check_all.py`，覆盖适配器的安全边界和合成命令流程。工作流语法/表达式可用官方 actionlint 对此 `.example` 文件显式检查。框架校验不运行此示例云端工作流、不上传镜像、不读取用户 Secrets。

本次验证及未验证范围见 [配套验证记录](../../validation/ci-cd-optional-template.md)，不能用旧版框架 CI 代替新增模板的真实项目试跑。

官方参考：[发布容器镜像](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images)、[环境保护与审批限制](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)、[部署与并发控制](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments)、[GHCR 访问与拉取认证](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)。上述配置不包含任何真实项目或部署凭据。
