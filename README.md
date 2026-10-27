# 开发前置框架 · Pre-development Framework

把软件需求、项目现状和团队职责，整理成可理解、可领取、可验收的开发准备包。

当前版本 **0.10.0-candidate.2**，面向公开试用。已有规则、模板和自动校验，跨项目效果仍待验证；不承诺适用于所有行业，也不把校验通过当作产品批准或实现验收。

## 适合谁

适合已有基本需求、希望在编码前明确范围、契约、分工与验收的个人或团队。可以由人、Codex 或其他能读取本地文件的助手使用，无需安装 Skill、Hook 或特定模型。输入不足时先澄清；小改动选择轻量路线。

只在用户显式调用时启用。终点为 Development Ready：不生成正式业务代码，不接管发布或运行；不规定后续开发必须使用什么模型、Skill、Agent、工具、编码方法或内部实现。

## 快速开始

需要 Git 和 **Python 3.9+**，工具仅使用 Python 标准库，不需要 pip、Node 或 API 密钥。Windows 可使用 `py -3` 替代命令中的 `python3`。

```text
git clone https://github.com/cbcraftlab/pre-development-framework.git
cd pre-development-framework
python3 -B scripts/check_all.py
```

轻量新需求：复制 [简短输入](templates/quick-input.json) 到自己的项目，填写项目 ID、需求、范围和验收；未确认的人员留空。将以下两个绝对路径替换为实际位置：

```text
python3 -B scripts/new_package.py --project-root "/absolute/path/to/project" --brief "/absolute/path/to/project/predev-input.json" --dry-run
python3 -B scripts/new_package.py --project-root "/absolute/path/to/project" --brief "/absolute/path/to/project/predev-input.json"
```

生成项目内草稿、结构化计划、HTML 阅读版和索引导航；状态固定为 `candidate + not_assessed + none`。不会替用户确认职责、批准基线或授权开发。该入口仅初始化 `new + light`；存量新增、需求变更和复杂需求见 [完整上手教程](docs/quickstart.md)。

## 把需求交给助手

使用 [通用调用提示](integrations/generic/ENTRY.md)，提供框架位置、目标项目根目录、需求来源和本次已确认职责。助手读取 [总体框架](FRAMEWORK.md) 和 [路线规则](routing/route-selection.md)，再按风险加载适用内容。框架不写入全局助手配置。

- [上手教程：从输入到批准、增量修改](docs/quickstart.md)
- [样例索引：轻量、标准、增量与完整路线](examples/README.md)
- [可选软件领域风险提示](profiles/software-risks.md)
- [可选 CI/CD 配套：Web＋服务器示例、部署与回滚准备](integrations/ci-cd/README.md)
- [字段及机器检查边界](protocol/machine-contract.md)
- [版本与兼容政策](docs/compatibility.md)
- [贡献方式](CONTRIBUTING.md)、[安全报告](SECURITY.md)、[MIT 许可证](LICENSE)

## 验证与维护

统一运行 `python3 -B scripts/check_all.py`：检查仓库、回归测试和所有落盘示例。单个项目包使用 `scripts/validate_project_package.py --project-root <绝对根目录> --package-dir <项目内相对路径>`。标准/完整路线保留可直接阅读的图表，HTML 从来源生成，不能独立维护结论。

已发布候选基线的 CI 在 Linux、macOS、Windows 和最低 Python 版本通过；最新提交以 [GitHub Actions](https://github.com/cbcraftlab/pre-development-framework/actions/workflows/validate.yml) 为准。CI/CD 配套的本地证据与未验证项见 [配套验证记录](validation/ci-cd-optional-template.md)。Windows 验证当前格式，冻结 0.9 仅支持 POSIX，详见兼容政策。自动门只证明已实现的结构规则，不证明模型行为、业务语义、批准真实性或减少返工的效果。

正式产物跟随目标项目，默认位置为 `docs/pre-development/<package-id>-<package-slug>/`。本仓库只保存规则、模板、合成示例和验证记录；更多说明见 [CHANGELOG](CHANGELOG.md)、[本版证据](validation/candidate-0.10.2-public-readiness.md)和[发布指南](docs/public-release.md)。

CI/CD 配套需在目标项目内另行选择、适配和启用。模板位于 integrations 下，复制本框架不会启用项目发布；本仓库自身的 Actions 仍只检查框架。配套不改变 Development Ready 的终点或授予部署权限。
