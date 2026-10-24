# AI 漫剧提示词工程 · Manju Engineering

面向中文 AI 漫剧的制作规范、提示词库与可运行工具。目标是让人物名字读得对、角色与道具保持连续、画面忠于剧本，并让每次生成和返工可以追溯。

[GitHub 仓库](https://github.com/w1nterdec/ai-manju-engineering) · [自动检查](https://github.com/w1nterdec/ai-manju-engineering/actions/workflows/ci.yml)

**当前版本：0.4.0 / M3。** 可追溯的成本估算、积分换算、四级预算预留与重试对账 尚未接入真实生成服务、未经过真实成片或行业评测。进度见 [STATE](docs/progress/STATE.md)。

## 从哪里开始

- **完全新手**：先读 [入门指南](docs/start-here.md)，复制 [提示词工作流](prompts/README.md)，手动完成一个镜头。
- **想实际制作**：使用下方命令生成镜头说明、配音清单和预览字幕，再交给自己选择的生成工具。
- **要开发大型项目**：阅读 [架构](docs/architecture.md)、[数据契约](docs/data-contract.md)、[模型适配规范](docs/providers.md) 与 [评测方案](docs/evaluation.md)。

## 五分钟运行

需要 Python 3.10+。核心工具只使用标准库，无需安装第三方依赖、GPU 或 API 密钥。请在仓库根目录执行；Windows 可按安装情况把 `python` 换成 `py`。

可以在 GitHub 使用 **Code → Download ZIP** 后解压，也可以运行 `git clone https://github.com/w1nterdec/ai-manju-engineering.git`，然后进入下载的目录。

```bash
python -m manju check examples/midnight_letter/episode.json
python -m manju build examples/midnight_letter/episode.json --out build/demo-v1
python -m manju check-series examples/midnight_letter/series/series.json
python -m manju plan build/demo-v1 --out build/preview.json --estimate
python -m manju run build/demo-v1 --out build/run --preview build/preview.json --auto-review-mock
python -m manju cost-report build/run
python -m unittest discover -s tests -v
```

出现“未提供角色参考图”警告是正常的：示例没有伪造参考图。`PASS` 仅表示剧本通过静态检查，不能代表音视频合格。

`build/demo-v1/` 会得到：

```text
manifest.json             构建版本、输入摘要、模板摘要与文件索引
episode.snapshot.json     本次构建使用的完整设定和剧本
shots/S001.md ...         逐镜头制作说明，包含人物、状态与剧情事实
voice_plan.json           原文字幕、配音文本、读音提示与待分配音色
subtitles.preview.srt     基于计划时间的字幕草稿，须按实测声音重新对齐
tasks.json                生成、复核、剪辑的依赖计划；当前没有执行器
```

输出目录不覆盖已有版本。再次构建请使用 `build/demo-v2` 等新目录。

## 三类常见问题如何处理

**人物名字读错**：建立完整姓名和术语词典，优先使用所选 TTS 支持的发音控制；字幕保留正确汉字，音色与姓名读音先做小样验收。ASR 可以筛查漏字、串台和文本偏差，但同音字或部分多音字错误仍需试听。见 [读音方案](docs/pronunciation.md)。

**画面瑕疵与角色漂移**：先批准角色参考图和关键帧，再生成短镜头；减少单镜头动作与主体数量；关键文字、钟面等用后期合成。负面提示词与固定 seed 都不能保证身份或肢体正确。见 [故障处理](docs/failure-cookbook.md)。

**剧情和画面不匹配**：原剧本是台词的唯一来源，分镜通过 ID 引用。检查节拍覆盖、台词归属、时间顺序和道具状态，再人工核对画面是否真的传达必需事实。结构覆盖率不等于叙事质量。

## 为实际媒体建立复核记录

```bash
python -m manju review-template build/demo-v1 --out build/demo-v1/review.json
python -m manju hash build/demo-v1/episode.snapshot.json
python -m manju gate build/demo-v1 build/demo-v1/review.json --source examples/midnight_letter/episode.json # expect: 1
```

上例 hash 演示对已有文件求摘要；实际复核时改成真实媒体路径。先实际生成并保存媒体，再填写复核人、带时区的时间、逐项结论以及实际文件 SHA-256。模板初始为 `pending`，此时 `gate` **应当失败**。详细操作见 [质量验收](docs/quality-gates.md)。

`gate` 检查人工记录是否完整、媒体是否仍是被审核的文件；它不自动观看媒体，不验证审核人身份，也不代替最终剪辑、字幕、混音和内容权利验收。

## 工程范围

已实现：严格 JSON 读取、字段与引用检查、单轨对白时序、剧情节拍覆盖、状态链、系列共享设定、跨集连续性、确定性计划编译、逐文件摘要、人工复核记录检查、CLI、回归测试和 GitHub Actions 配置。

后续建设：真实 TTS/图像/视频适配器、媒体探测与对齐、任务队列、重试及预算、依赖失效重建、素材版本库、Web 工作台、真实成片评测。适配接口目前只是扩展契约，不代表这些服务已经接通。

题材、画幅、风格与模型分开配置。题材差异见 [多题材手册](docs/genre-playbook.md)，模型能力证据见 [参考资料](docs/references.md)。

## 参与和许可

[贡献指南](CONTRIBUTING.md) · [路线图](ROADMAP.md) · [更新记录](CHANGELOG.md) · [MIT 许可证](LICENSE)

代码、本文档、提示词及原创示例按 MIT 开放。外部模型、音色和第三方素材按各自条款使用；模型接入不自动授予声音或角色素材的使用权。
