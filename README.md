<div align="center">

# 个人 AI 短剧与漫剧创作指南

**从第一条样片开始，把想法变成镜头**

![Guide](https://img.shields.io/badge/%E5%88%9B%E4%BD%9C%E6%8C%87%E5%8D%97-AI%20%E7%9F%AD%E5%89%A7-9B59B6) ![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white) [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

创作线路 · 提示词 · 工具目录 · 制作包

[开始第一条样片](docs/creator-guide/01-first-film.md) · [选择线路](docs/creator-guide/02-workflow.md) · [提示词库](prompts/README.md) · [工具目录](docs/creator-guide/06-tools.md)

</div>

---

面向中国大陆个人创作者：复用现有工具，组织自己的生成线路，并在实际制作时查步骤、复制提示词、记录尝试和定位返工。

围绕三个问题展开：**姓名读错、画面瑕疵与角色不一致、剧情和分镜不匹配。**

本项目以实操指南为主，附可选的本地辅助脚本。实际图片、视频、配音和剪辑在你选择的现有平台完成；不要求先搭建自己的创作平台，也不要求会写代码。

[开始第一条样片](docs/creator-guide/01-first-film.md) · [三条生成线路](docs/creator-guide/02-workflow.md) · [工具网站目录](docs/creator-guide/06-tools.md) · [复用与 fork](docs/creator-guide/07-reuse-and-fork.md) · [提示词库](prompts/README.md)

## 先选一条适合自己的生成线路

- **图片动态漫 motion_comic**：豆包或 DeepSeek 整理剧本 → 即梦生成角色与镜头图 → 试听配音 → 剪映推拉、局部动态、字幕和终剪。无需每镜头都生成视频。
- **逐镜视频短剧 story_video**：剧本与参考资产 → 批准关键图 → 选一个主视频工具逐镜生成 → 筛选与局部返工 → 配音及剪映后期。
- **一站式创作 agent_first**：小云雀导入剧本 → 确认全局角色与场景 → 故事板和片段生成 → 重拍问题片段 → 导出后审片与终剪。

第一次先做 30—60 秒、5—8 个镜头的小样。原创[《雨夜来信》](examples/creator/README.md)提供了六镜头、46 秒的可编辑文字样例，尚无实际生成媒体。

## 不写代码时怎么使用

1. 按[第一条样片](docs/creator-guide/01-first-film.md)准备剧本、角色、场景和姓名读音。
2. 从[提示词库](prompts/README.md)复制任务对应的模板，填入原文与参考要求。
3. 到工具官网实际生成，先审核关键图，再处理需要动态的镜头。
4. 保存选用和废弃版本，遇到问题查[最小返工](docs/creator-guide/03-quality-and-repair.md)。
5. 在剪映组织声音、字幕和画面；[完整审片与发布准备](docs/creator-guide/05-publishing.md)。

## 可以直接使用的工具网站

- 剧本讨论：[豆包](https://www.doubao.com/)、[DeepSeek](https://www.deepseek.com/)。
- 图片与视频：[即梦](https://jimeng.jianying.com/)、[可灵中文站](https://klingai.kuaishou.com/)、[Vidu 中国站](https://www.vidu.cn/)、[海螺国内入口](https://hailuoai.com/video/create)。
- 一站式短剧与漫剧：[小云雀](https://xyq.jianying.com/)。
- 配音与终剪：[讯飞智作](https://peiyin.xunfei.cn/)、[剪映](https://www.jianying.com/)。
- 进阶工作流：[LiblibAI](https://www.liblib.art/)、[ComfyUI](https://github.com/Comfy-Org/ComfyUI)。

[完整工具卡](docs/creator-guide/06-tools.md)记录适用环节、官方帮助、使用边界和核对日期；机器可读目录在 [catalog/tools.json](catalog/tools.json)。不把网页会员当 API 额度，不按导航站或课程宣传推断价格与效果。

## 复用或 fork 现有平台

[Toonflow](https://github.com/HBAI-Ltd/Toonflow-app)是本轮优先评估的创作工作台候选；[ComfyUI](https://github.com/Comfy-Org/ComfyUI)可作为进阶生成执行层。具体固定版本、许可证、外部模型依赖和自部署要求，见[复用与 fork 指南](docs/creator-guide/07-reuse-and-fork.md)及[catalog/reuse.json](catalog/reuse.json)。

复用产品有三种不同动作：使用其网站、调用其官方接口、按许可证 fork 源码。仓库目前只提供引用与交接，不声称已部署、已 fork 或接通这些服务。

## 可选的本地自动化

需要批量整理制作资料时，在仓库根目录使用 Python 3.10+；这组命令只使用标准库，不联网、不扣生成费用。

```bash
python -m manju creator routes
python -m manju creator tools --stage video
python -m manju creator new --route motion_comic --out build/first-film
python -m manju creator check build/first-film
python -m manju creator pack build/first-film --out build/first-film-pack-v1
python -m manju creator verify-pack build/first-film-pack-v1
```

编辑输入文件后重新导出到新版本目录。打开制作包中的 `index.html` 或 `README.md`，可查看工具入口、逐镜卡、图片和视频提示词、配音清单、计划字幕、审核表和尝试记录。

脚本会检查台词原文、说话人、唯一分配和顺序、角色与场景引用、完整姓名读音登记；不会自动判断画面是否好看、姓名实际读对或剧情已经被观众理解。字幕按计划时长生成，需在配音与终剪后对齐。审核表默认全部待办。

更多操作见[本地自动化与数据约定](docs/creator-guide/08-automation.md)。冻结制作包供追溯，填写尝试与审核时使用工作副本，再保存实际素材和版本。

## 项目结构与当前边界

- [docs/creator-guide/](docs/creator-guide/README.md)：个人实操指南，是主入口。
- [prompts/](prompts/README.md)：按任务复制的提示词。
- [examples/creator/](examples/creator/README.md)：可编辑原创短片。
- [catalog/](catalog/README.md)：国内工具、生成线路和开源复用目录。
- `manju/creator.py` 与 `creator_cli.py`：可选制作包辅助。
- [旧工程工具](docs/engineering/README.md)：原 CLI、mock 执行、预算、血缘与交付契约，保留兼容并标为进阶选项。

当前版本 **0.9.0** 表示本次“个人指南与制作包”重构，不等同于旧路线中候选 0.9 的实媒平台能力已完成。当前没有真实厂商适配器、自动登录、无人值守出片、平台自动发布或已验证商业样片。

## 后续怎样改进

先依据一次实际制作补充失败样本和最少返工，再决定是否需要一个官方 API 或可复用开源工作流。保持指南能脱离代码独立使用，不再将建设全链路工业平台作为前置任务。[当前路线](ROADMAP.md) · [方向变更说明](docs/decisions/0012-personal-creator-guide.md)

开发检查：Python unittest、[指南链接与目录检查](tools/check_guide.py)、[隔离示例验证](tools/verify.py)。原有历史审查与工业平台计划保留为背景，不是当前执行路线。

代码、文档、提示词和原创示例按 [MIT](LICENSE) 发布；引用平台、模型、音色、素材及第三方源码分别遵守各自条款。
