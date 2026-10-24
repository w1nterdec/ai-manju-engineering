# 剪辑交接与交付包

`handoff` 输出时间线 CSV/JSON 与 SRT。无 alignment 时是计划草稿，有 alignment 时按实测音频；视频需要重新剪辑的提示不能忽略。格式为通用清单，尚未验证 Premiere、DaVinci、CapCut 工程交换格式。

`package --demo --run ...` 输出可独立校验的模拟包，包含源快照、镜头提示词、任务血缘、模拟媒体、质量和授权记录、AI 元数据、修改事件与静态客户报告。mock 不是真实配音或视频，包内醒目标记不可作为客户成片。成本默认隐藏，只有 --include-costs 才导出。

生产模式不加 --demo，需同时提供 --config、--review、--final、--alignment、--provenance。授权不完整、mock、实际视频技术检查未通过、人工审核缺失或 AI 标识记录缺失，都会阻断打包。可以使用其他工具手工制作真实媒体，但须自行保留实际生成信息，工具不会索要密钥。

provenance_version 为 1.0，含 manifest_sha256、shots、final。shots 按镜头 ID 保存实际 provider、model、parameters、prompt（实际提交文本）、prompt_sha256、source_prompt_sha256（批准镜头说明）、input_asset_ids、video_sha256、有对白时 audio_sha256；final 保存 sha256、editor、tool 和可选 settings。所有实际媒体须与人工记录一致；素材 ID 须已通过授权检查。上述都是记录机制，不提供法律或事实真实性保证。

AI 标识配置 ai_label 需记录 platform、disclosure、verified_by、as_of、source_url。字段和实际显隐标识需由使用者按所在地区和投放平台最新要求核实；本工具不向任何平台发布，也不自动添加隐形水印。

`verify-package 目录` 只需本包与标准库即可验证文件完整性。目录不能覆盖。没有真实客户样本和实际视频探测通过记录时，不应将本项目称为已完成商业成片验证。

0.8.2 起，交接与生产包会校验完整对齐契约：原顺序覆盖全部镜头/台词、连续镜头边界、测量长度和音频摘要、总时长及规范 SRT。工具新生成报告还记录字幕 SHA-256；旧报告可无该字段，但其完整内容仍必须通过核对。延长的镜头按验证后的时间线检查，quality-report 可用 --alignment 指定。
