# 复用现有创作平台和自己的自动化

核对日期：2026-10-25。本项目的主体是个人制作指南、线路和交接记录。已有平台负责画布、生成或剪辑时，优先复用；自己只补缺少的制作准备、质量核对和文件交接。本轮核对了原仓库与许可证，没有创建远端 fork、下载安装或执行第三方代码。

## 先决定你需要哪种复用

1. **直接使用网站**：在即梦、小云雀、可灵、Vidu 等个人产品中制作并导出素材。自己的流程负责提示词、文件命名、版本和审核记录。网站可使用不代表可以复制它的代码或页面产品。
2. **独立部署已有应用**：保留上游工作台，把制作包和导出素材交给它。先跑通一个项目，再判断是否需要修改上游。
3. **复用公开接口**：有正式 API 或本地工作流接口时，编写小适配层。网页会员、API 权限和调用费用分别确认；不要依赖未公开内部接口。
4. **维护自己的 fork**：确实需要修改画布、数据或任务逻辑时，再固定版本建立 fork。上游更新、依赖和许可证维护也由自己承担。

前三种方式能满足需要时，不必立即维护整套平台代码。

## 优先评估 Toonflow

原仓库：[HBAI-Ltd/Toonflow-app](https://github.com/HBAI-Ltd/Toonflow-app)。本次固定提交为 `30139c931e80476caa718b31684b86383c6e83ce`。

[该版本 README](https://github.com/HBAI-Ltd/Toonflow-app/blob/30139c931e80476caa718b31684b86383c6e83ce/README.md)说明它用无限画布组织剧本、角色场景、图片和视频，并可自行配置模型。它适合评估为自己的创作工作台，减少从零建设这些功能的工作。[该版本 LICENSE](https://github.com/HBAI-Ltd/Toonflow-app/blob/30139c931e80476caa718b31684b86383c6e83ce/LICENSE)是 **MIT**，要求保留版权与许可通知。

**大陆访问备用来源**：上述固定版本 README 同时列出 [Gitee 仓库](https://gitee.com/HBAI-Ltd/Toonflow-app)和 [AtomGit 仓库](https://atomgit.com/HBAI-Ltd/Toonflow-app)。这是上游提供的备用地址，本轮没有下载或验证各站点的同步情况。使用时核对实际提交和 LICENSE，以原仓库及所选固定版本的许可为准，不把备用站点名称当成版本一致或持续可访问的保证。

建议按下面顺序试用和决定：

- 从原仓库确认系统要求、安装包、模型配置和数据目录，使用一个无敏感信息的小项目。
- 先验证中文剧本、角色参考、5 至 8 个镜头、素材下载是否符合需求，不先改平台架构。
- 记录至少一个实际阻碍，例如需要导出固定镜头 ID，或想把自己的审核清单带进画布。
- 只有这些改动需要源码支持时，才在自己的账户建立 fork，保存上游远端、固定提交、许可证与改动记录。
- 将接口约束、提示词、素材映射和检查表保留为独立文件，方便以后更换工作台。

代码 MIT 许可不等于其中使用的模型、插件、图片、音色或 API 都能免费商用。所选历史版本也可能采用不同许可，必须以实际固定版本为准。README 里的赞助链接与活动价不作为本项目推荐依据。

## ComfyUI 适合作为生成执行层

原仓库：[Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI)。固定提交 `19ae172bff6c9e4c738e7f2e00fe087f5b5b46ab` 的[README](https://github.com/Comfy-Org/ComfyUI/blob/19ae172bff6c9e4c738e7f2e00fe087f5b5b46ab/README.md)介绍可复用节点图和本地 API；[LICENSE](https://github.com/Comfy-Org/ComfyUI/blob/19ae172bff6c9e4c738e7f2e00fe087f5b5b46ab/LICENSE)为 **GPL-3.0**。

适合把反复使用的生图、局部修补或视频步骤保存为工作流。先独立运行，通过文件或公开接口交接；分发修改后的软件时按 GPL 履行通知、对应源码等义务，不把其软件代码直接按本仓库 MIT 重新发布。模型权重、LoRA、社区节点和在线模型服务继续单独核对。生成画面本身的权利也不能仅凭软件 GPL 得出结论。

第一次制作没有固定工作流时，可以继续使用网页工具；有明确重复任务后再加入这一层。

## NarratoAI 可作为后期参考

原仓库：[linyqh/NarratoAI](https://github.com/linyqh/NarratoAI)。固定提交 `29a11b6cdf61b69ba90321fc5babc160e0ca2657` 的[README](https://github.com/linyqh/NarratoAI/blob/29a11b6cdf61b69ba90321fc5babc160e0ca2657/README.md)面向影视解说、剪辑、配音和字幕；[LICENSE](https://github.com/linyqh/NarratoAI/blob/29a11b6cdf61b69ba90321fc5babc160e0ca2657/LICENSE)为 **MIT**。

如果你已经有可合法使用的视频，想研究解说、音频或剪辑交接，可以参考它。它不直接替代原创角色短剧的前期设定与逐镜生成。配置中的外部模型、声音和视频素材仍需有对应使用条件，不因代码开源就获得影视二创素材的授权。

截至核对，上述 Toonflow、ComfyUI、NarratoAI 原仓库公开且未归档；这是仓库状态观察，不是安装成功、效果或代码安全结论。

## 不宜作为默认商业 fork 的候选

**火宝短剧**原仓库为 [chatfire-AI/huobao-drama](https://github.com/chatfire-AI/huobao-drama)。固定提交 `26de7df59806588e98e103a21bd0bfd26d4a55a6` 的[LICENSE](https://github.com/chatfire-AI/huobao-drama/blob/26de7df59806588e98e103a21bd0bfd26d4a55a6/LICENSE)实际是 **CC BY-NC-SA 4.0**，包含非商业与相同方式共享条件。可以作为流程研究候选；不能因为仓库公开就默认允许商业部署和再分发。个人接单、盈利内容或平台经营不自动属于非商业用途，实际使用范围需获得相符授权。

**waoowaoo** 的[当前原仓库 LICENSE](https://github.com/waooAI/waoowaoo/blob/main/LICENSE)是 **Elastic License 2.0**，限制向第三方提供具有实质功能的托管或管理服务。本项目不把它列为可无条件改造成商业 SaaS 的标准开源底座。这个条目用于说明“公开源码”和“无额外商业限制”不同，不是已核验部署推荐。

机器可读的四个候选和固定许可来源见 [catalog/reuse.json](../../catalog/reuse.json)。

## 自己的自动化只做有价值的连接

无论使用哪家工作台，保持同一套镜头和台词 ID。自己的制作包至少带上原剧本、角色与读音资料、分镜、参考版本、提示词和审核清单；生成结束后登记实际文件、模型、尝试与费用，再进入剪辑。

优先自动化重复且明确的动作：整理文件、生成逐镜提示词、检查缺失记录、列出待返工镜头、准备交接资料。对外生成只有在正式接口、权限、费用和错误恢复边界明确后才接入。最开始的人工作品判断、姓名试听和最终审片仍由你确认。

复用检查记录建议包含：上游仓库、固定提交、许可证链接、选用方式、需要的外部服务、数据能否完整导出、自己修改的文件，以及下一次核对日期。这样以后更换工具时，制作经验和素材记录仍属于自己的工作流。
