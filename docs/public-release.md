# 公开候选版发布指南

本指南准备公开材料，不自动提交、推送、打标签或切换可见性。

## 发布前

1. 在干净交付副本运行 `python3 -B scripts/check_all.py`，打开 HTML 核对图表，审阅最终 diff。
2. 确认 MIT 许可证、版权归属和材料公开权。文档只保留框架层面的公开摘要，案例使用虚构 Web 端与服务器，不带公司项目名称、路径、业务流程、数据或真实图。
3. 核对 Git 历史、作者邮箱、分支、Issue、附件和 Actions。发布前来源仓库的旧提交若含内部内容，必须继续隔离在私有仓库；从审阅后的源文件建立独立新历史。本版已采用此隔离方式，公开历史不继承原私有提交。后续不要把私有历史合并或推送到公开仓库。
4. 上传后等待 CI 实际结果；工作流文件存在不等于 Linux/macOS/Windows 已通过。核对兼容影响与已知限制。
5. 仓库所有者批准精确提交、许可证及公开范围后，再进行 Git 交付和可见性切换；启用可用的私密漏洞报告渠道。发布说明保持“公开试用候选版”。

GitHub 官方说明：[许可证](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)、[可见性影响](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)。

## 公开后

记录不同项目、独立使用者的耗时、澄清、遗漏、契约重定与返工。固定行为评测仍须实际执行，合成示例不冒充真实效果。按 [验证计划](../validation/framework-validation-plan.md) 决定限定范围的稳定版晋级。
