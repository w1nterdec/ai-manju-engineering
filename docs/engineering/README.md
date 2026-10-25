# 旧版离线工程工具参考
> 这是 0.8.2 工程功能的兼容参考，已退出新手主入口。请先阅读[个人创作指南](../creator-guide/README.md)；无需运行本页的 mock 管线才能开始创作。四项历史边界仍见[原审查](../audits/2026-10-25-project-review.md)，本次指南重构不等于这些缺陷已修复。


面向中文 AI 漫剧的制作规范、提示词库与离线工程工具：管理姓名读音、角色与道具连续性、分镜和剧本关联，以及生成任务、预算、授权和交付记录。

[GitHub 仓库](https://github.com/w1nterdec/ai-manju-engineering) · [CI](https://github.com/w1nterdec/ai-manju-engineering/actions/workflows/ci.yml) · [入门指南](../../docs/start-here.md) · [路线图](../../ROADMAP.md)

**当前版本：0.8.2。** M0–M7 的离线工程功能已实现；M8 只读看板经评估暂缓。内置适配器均为 mock，尚未接入真实生成服务，也没有真实成片、客户交付或行业对比评测结果。

## 适合怎样使用

- **新手学习**：从 [入门指南](../../docs/start-here.md) 和 [提示词流程](../../prompts/README.md) 开始，先制作并审核一个镜头。
- **制作人员**：用结构化剧本统一人物、读音和分镜，导出制作说明；在自行选择的实际工具中制作，保留来源、审核与授权记录。
- **工程开发**：阅读 [架构](../../docs/architecture.md)、[数据契约](../../docs/data-contract.md)、[适配规范](../../docs/providers.md) 和 [评测方案](../../docs/evaluation.md)。

核心运行只需 **Python 3.10+ 标准库**，无需 GPU、第三方 Python 包或 API 密钥。真实视频探测可选安装 ffprobe；完整发布扫描需要 Git。Windows 可按安装情况把 `python` 换成 `py`。

下载 GitHub 的 **Code → Download ZIP** 并解压，或使用 `git clone https://github.com/w1nterdec/ai-manju-engineering.git`。以下命令均在仓库根目录执行。

## 最小开始：检查与编译

```bash
python -m manju check examples/midnight_letter/episode.json
python -m manju build examples/midnight_letter/episode.json --out build/demo-v1
python -m manju check-series examples/midnight_letter/series/series.json
```

示例未提供角色参考图，因此出现相应警告是正常的。`check` 的 PASS 只表示静态检查通过，不能证明名字读音、画面或成片质量。

`build/demo-v1/` 包含以下制作计划：

```text
manifest.json             版本、输入摘要与文件索引
episode.snapshot.json     冻结的设定和剧本
shots/S001.md ...         逐镜头制作说明、状态与剧情事实
voice_plan.json           原文字幕、配音文本与读音提示
subtitles.preview.srt     基于计划时间的字幕草稿
tasks.json                兼容旧格式的依赖计划，供执行器展开
```

构建、预览、对齐和交付输出不覆盖已有版本。再次运行时使用新目录，如 `build/demo-v2`。

## 完整离线演示：执行到交付

先完成上面的编译，再执行：

```bash
python -m manju plan build/demo-v1 --out build/preview.json --estimate
python -m manju run build/demo-v1 --out build/run --preview build/preview.json --auto-review-mock
python -m manju cost-report build/run
python -m manju demo-audio-map build/run --out build/audio-map.json
python -m manju align build/demo-v1 build/audio-map.json --out build/aligned
python -m manju quality-report build/demo-v1 --run build/run --alignment build/aligned --out build/quality.json
python -m manju handoff build/demo-v1 --alignment build/aligned --out build/handoff
python -m manju package build/demo-v1 --run build/run --demo --alignment build/aligned --out build/delivery
python -m manju verify-package build/delivery
```

图像、视频等 mock 产物是带元数据的占位说明，mock 配音是用于时长测量的静音 WAV。`--auto-review-mock` 只模拟审核，未加该开关时执行器会在人工节点暂停。`DEMO` 成本为配置中的模拟数值，**不是厂商价格或真实账单**。

可查看 `build/delivery/report.html` 和 `package-manifest.json`。独立校验只检查文件完整性；演示包不能作为客户成片或实际验收结果。`--allow-network` 不会启用真实适配器，本发行版仍拒绝真实生成调用。

## 四种业务画像

画像是 [可校验配置](../../configs/profiles)，决定表单、成本口径、交付物与特有检查：

- `series_drama`：连续剧集、跨集人物与道具、每分钟/每集成本。
- `ad_batch`：商品清单、多个开头钩子、变体血缘、共享批次预算。
- `client_service`：人工与返工参数、修改轮次、报价辅助、客户验收模板。
- `shoppable_export`：SKU、HTTPS 链接和时间点元数据，仅导出文件。

```bash
python -m manju new --profile series_drama --out build/series-project
python -m manju new --profile ad_batch --out build/ad-project
python -m manju new --profile client_service --out build/client-project
python -m manju new --profile shoppable_export --out build/shoppable-project
python -m manju batch build/ad-project examples/business/products.csv --out build/ad-batch --execute --auto-review-mock
python -m manju quote --profile client_service --inputs examples/business/cost-inputs.json --out build/quote.json
python -m manju shoppable-export examples/business/shoppable.json --out build/shoppable.json
```

报价完全按输入参数计算，示例不是市场价格、收入预测或盈利保证。商品示例不连接店铺；项目不实现转售、订阅计费、多租户 SaaS、直播或平台自动发布。见 [成本口径](../../docs/commercial/profiles-and-costs.md) 与 [作业和风险](../../docs/commercial/operations-and-risks.md)。

## 你关心的三个质量问题

**名字读错**：保存完整姓名、术语和作者确认的目标读音，按实际 TTS 能力转换控制语法，固定音色并逐句试听。更换身份/音色资产会使对应配音与下游审核失效。字幕保留正确汉字，不能把纠音替换文字直接写进字幕。见 [读音方案](../../docs/pronunciation.md)。

**画面瑕疵**：先批准角色参考图与关键帧，再生成短镜头；减少复杂互动，关键文字与钟面可用后期合成。参考图、负面描述或固定 seed 都不能保证每次生成正确，仍需观看完整视频。见 [故障处理](../../docs/failure-cookbook.md)。

**剧情不匹配**：原剧本是台词唯一来源，分镜通过 ID 引用；检查剧情覆盖、台词顺序、画面内说话人和状态链，再核对成片是否真正传达事实。结构覆盖不等于叙事质量。

## 实际媒体的审核与交付

以下命令创建待审核记录并演示求摘要；尚未填写和提供实际媒体时，最后一条应当退出 1：

```bash
python -m manju review-template build/demo-v1 --out build/demo-v1/review.json
python -m manju hash build/demo-v1/episode.snapshot.json
python -m manju gate build/demo-v1 build/demo-v1/review.json --source examples/midnight_letter/episode.json # expect: 1
```

实际使用时，hash 改为真实媒体路径，填写实际审核人、带时区时间和具体证据。`gate --production-config` 额外检查素材/声音授权记录；生产打包还要求最终视频、完整实测时间线、来源、AI 标识和画像检查。mock、缺失记录或未完成的技术检查会阻断生产包，详见 [质量验收](../../docs/quality-gates.md) 和 [交付规范](../../docs/delivery.md)。

实测配音导致镜头延长时，按新时间线重新剪辑视频，并给 `quality-report` 传入 `--alignment`。交接与打包会核对全部镜头、台词、测量和字幕，拒绝空时间线或被改写的 SRT；旧版工具生成的完整对齐记录仍可使用。

授权、AI 标识和审核均为记录检查机制，不提供法律结论、审核人身份认证或数字签名。具体要求以所在地区及投放平台最新规则为准，由使用者核实；最终成片仍须客户验收。

## 当前边界与后续工作

已实现离线执行恢复、幂等与局部重建、四级预算、素材批准与授权记录、血缘、逐句实测字幕、通用剪辑交接、交付包校验及四种画像。核心保持零第三方依赖，episode 0.1 和原有命令保持兼容。

尚未验证真实厂商服务与账单、真实成片效果、客户交付、大规模负载或多机协作；未实现字级/口型对齐、批次整体恢复、可信签名和只读看板。ASR 目前是能力接口与已提供转写的文本筛查函数，不能证明多音字读对。

下一阶段先修复审查发现的边界并验证本地实媒，再依据所选服务的官方文档接入真实适配器，用原创短片验证整条链路。凭据由使用者在自己的授权环境保管，不提交仓库。见 [路线图](../../ROADMAP.md)、[人工待办](../../docs/HUMAN_TODO.md) 和 [进度记录](../../docs/progress/STATE.md)。

## 项目审查与成长路线

[2026-10-25 审查](../../docs/audits/2026-10-25-project-review.md) 在既有测试之外复现四项 P2，目前尚未修复：素材拷贝中断、画像保留名、额外素材失效链和演示包血缘核对。审查不等于新增能力，96 测试通过也不表示没有漏测边界。

[候选成长路线](../../docs/growth/2026-10-25-roadmap.md) 先修复这些边界，再验证本地实媒、单个中文纠音 TTS、受控视觉链和小团队交付。版本为候选计划，真实模型效果、价格和客户结果仍需实际证据。

## 开发、贡献与许可

```text
python -m unittest discover -s tests -v
```

CI 覆盖 Windows/Linux 与 Python 3.10、3.12、3.14，并在隔离目录执行全部 README 示例。发布前另运行 `python tools/secret_scan.py` 和 `git diff --check`；扫描工具不是零遗漏证明。

[贡献指南](../../CONTRIBUTING.md) · [更新记录](../../CHANGELOG.md) · [官方参考资料](../../docs/references.md) · [MIT 许可证](../../LICENSE)

代码、文档、提示词与原创示例按 MIT 开放。外部模型、音色和素材按各自条款使用；模型接入不自动授予声音或角色素材的使用权。
