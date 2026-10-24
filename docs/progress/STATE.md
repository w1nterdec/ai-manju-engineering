# 自治进度

当前阶段：2026-10-25 项目审查与成长路线已整理；运行时仍为 0.8.2。96 项既有测试、23 条 README 示例和扫描通过，另有四项已复现 P2 待修。

## 已完成

基线 15c5e58 → M0 64d51ec → M1 2d0912d → M2 c84c3eb → M3 bfe2a02 → M4 a2f85fb → M5 fceb139 → M6 4ff7892 → M7 5e65716。范围见 ROADMAP.md。上述里程碑开发期间未直接改动 main；后续授权合并进度以 PR 状态为准，PR 为 https://github.com/w1nterdec/ai-manju-engineering/pull/1。

87 项本地 unittest 通过；README 23 条离线命令在隔离目录按预期退出。M0–M4 与 M6、M7 的跨系统 CI 已通过；M5 已包含在 M6 正常快进推送中并经后续测试覆盖。收尾功能快照 3154200 的 push 和 PR 两轮完整 CI 均通过；M5–M8 标签按决策 0010 统一绑定最终验证快照。

## 0.8.1 离线里程碑结果（历史）

当前没有待实现的 M0–M7 任务。M8 仅评估、不增加界面。87 测试与 23 README 命令已再次通过，历史/暂存扫描和打包边界已复核。演示 build/final-demo-v081 完成 19 个 mock 任务和独立包校验。

下一阶段需要真实样本、厂商文档、授权和实际客户验收，见 HUMAN_TODO.md；不应再次从 M0 重做。未引入真实适配器、付费调用、第三方核心依赖或禁止的业务模式。

## 已知限制

无真实生成适配器，无真实密钥或付费调用；无真实视频/音色/客户效果评测；本机无 ffprobe（可选探测路径及离线参数用注入测试验证）；ASR 仅接口和文本筛查，字幕为逐句测量而非字级/口型对齐；授权和人工记录不提供身份签名或法律判断；批次整体恢复尚未实现；看板暂缓。

M5 首次推送因发布步骤重叠发生非快进拒绝；M6 随后正常快进推送已包含 M5。没有强推或改写历史；后续发布步骤串行执行。沙箱进程启动器 refresh 故障，使用已批准的执行环境完成命令；未修改全局 Git 配置。

## 0.8.1 验证与推送（历史）

命令：python -m unittest discover -s tests -q（87 passed）；python tools/verify.py（23 README examples，包含 pending gate 预期退出 1）；python tools/secret_scan.py；git diff --cached --check。最终记录以收尾提交的 CI 为准。

最近已核验功能推送：codex/autopilot `315420066fb31e4e435e3b1c38694397fb42f3be`，核验时间 2026-10-24T20:35:38+08:00。后续状态提交不自引用自身 SHA：确切最终提交取 git log、远端分支和里程碑标签，避免不可实现的摘要固定点。

## 决策索引

0001 离线/兼容与顺序；0002 能力侧契约；0003 事务与恢复；0004 预算预留；0005 资产与授权；0006 测量边界；0007 交接与包；0008 画像配置；0009 看板暂缓。全部位于 docs/decisions/。

## M8 / 0.8.1（历史）

离线生产工作流收尾验证；只读看板评估完成并暂缓实现

最近一次已核验推送：codex/autopilot `5e657164aaa918b49ea945a54cd10d49c75dec75`，核验时间 2026-10-24T20:26:22+08:00。本次提交 SHA 以 git log 和里程碑标签为准，避免在提交内容中自引用自身摘要。

最终发布以 codex/autopilot、milestone-M0–M8 与 PR #1 的实际引用和 CI 为准；本记录提交自身摘要由 Git 提供，不伪造自引用 SHA。决策索引新增 0010：收尾验证快照与标签。

## 2026-10-24：用户授权检查后合并并更新 README

最新明确授权覆盖 PR #1 先前“不得自行合并”的限制；仅允许本轮在复查和 CI 通过后通过 GitHub 合并，仍不直接推送 main、不强推、不改历史。

复查发现并修复四项：TTS 身份依赖、实测延长镜头的时长检查、完整对齐/SRT 校验、合并后空历史范围扫描。新增回归测试；版本 0.8.2，旧 episode 和 CLI 兼容。README 按新手入口、完整模拟流程、画像和实际交付重新编排。

合并采用 merge commit，以保留已发布里程碑和全部功能提交。验证命令为完整 unittest、tools/verify.py、tools/secret_scan.py 与 git diff --check；最终合并提交和实时检查结果以 PR #1、origin/main 为准，不在提交内伪造自身摘要。

本轮合并前本地验证结果：96 项 unittest 全部通过；23 条 README 命令均按预期退出；扫描和空白检查通过。合并前必须等待本轮新提交的全部远端 CI 完成，合并后核对 main 的检查。

## 2026-10-25：项目审查与成长路线

基线 main d25bbd623b66045edec87d2c5a1b60b63740fbf9，与远端一致，PR #1 已合并且 main CI 成功。本轮仅更新审查证据和路线，没有修改运行时、使用密钥或调用生成服务。

四项 P2 已用合成文件复现：A1 素材拷贝中断阻止重试；A2 自定义模板覆盖核心配置；A3 额外素材变更不使相关任务 stale；A4 演示包外层完整性通过但内容不匹配血缘。详见 docs/audits/2026-10-25-project-review.md、对应证据与复现脚本。A4 未证明实际生产门禁可绕过。

下一任务：候选 0.8.3 修复 A1–A4 并转为回归测试，然后推进候选 0.9 的本地实媒导入和验证。这些工作不依赖真实密钥；实际生成、授权与客户验收仍按 HUMAN_TODO 由使用者提供证据。

本轮在 codex/autopilot 上整理审查文档，保持 main 原样；新草稿 PR 不适用上一轮仅针对 PR #1 的合并授权。新增决策 0011，候选版本仍是计划。

验证：python -m unittest discover -s tests -q（96 passed）；python tools/verify.py（23 命令按预期退出）；python tools/secret_scan.py（passed）；审查复现四项 reproduced=true。ffprobe/ffmpeg 的 PATH 查询未找到工具，不作为测试失败或已完成实媒验证。

本轮最近已核验推送：codex/autopilot `852b29cb34f0603852030ebc37a700ced4c3c644`，2026-10-25T00:32:34+08:00，远端与本地一致。审查草稿 PR：https://github.com/w1nterdec/ai-manju-engineering/pull/2 。后续仅追加本状态记录，不在提交内容中自引用自身摘要；最终引用以 Git 和 PR 为准。
