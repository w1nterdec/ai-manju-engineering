# 自治进度

当前里程碑：M0 基线审计完成，进入 M1 能力层。日期：2026-10-24，Asia/Singapore。

已完成：核对 origin 正确、工作区干净；从 main 15c5e58 创建 codex/autopilot；审计源码/文档/示例；原有 38 项测试和离线 README 命令验证；建立审计、决策与人工待办。

进行中：M1 注册表、全层 mock、能力与身份资产、镜头路由。

后续顺序：M1 能力 → M2 执行/恢复 → M3 预算 → M4 资产/授权 → M5 媒体/质量 → M6 交付 → M7 四画像 → M8 条件评估。每阶段保留旧契约，独立提交、验证、标签和推送。

已知问题：真实服务、真实媒体与实际授权均不存在；所有后续开发默认 mock。沙箱启动器 refresh 故障，使用经审批的执行器完成本地命令，未修改全局 Git 配置。

最近验证：python -m unittest discover -s tests -q（38 passed）；python tools/verify.py（见本里程碑验证日志，提交前运行）。

最近推送：本阶段尚未推送；基线远端 main 15c5e58。下一次推送后追加确切分支、哈希和带时区时间。

决策索引：[0001](../decisions/0001-offline-production-core.md)。人工事项：[HUMAN_TODO](../HUMAN_TODO.md)。
