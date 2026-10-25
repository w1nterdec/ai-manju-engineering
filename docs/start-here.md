# 从第一条作品开始

这个项目现在首先是一份面向中国大陆个人作者的 **AI 短剧与漫剧创作指南，以及自己的自动化工作流参考**。先使用现有工具完成作品，不要求先部署平台或理解工程契约。

## 你现在想做什么

- **还没有做过完整作品：**从 [第一条 30—60 秒样片](creator-guide/01-first-film.md)开始。
- **已有剧本：**选 [图片动态漫、参考图到视频或一站式 Agent 线路](creator-guide/02-workflow.md)。
- **名字读错、画面有瑕疵、剧情不匹配：**查 [质量检查与局部返工](creator-guide/03-quality-and-repair.md)。
- **素材和版本混乱：**复制 [制作记录](creator-guide/04-production-records.md)。
- **已经做完成片：**查 [发布准备](creator-guide/05-publishing.md)。
- **需要可复制的提示词：**打开 [提示词库](../prompts/README.md)。
- **想运行本地自动化：**按 [根目录 README](../README.md)当前提供的入口操作。

## 最省工具的起步组合

图片动态漫可以先用 [豆包](https://www.doubao.com/)或 [DeepSeek](https://www.deepseek.com/)整理文本，[即梦](https://jimeng.jianying.com/)做参考与图片，[剪映](https://www.jianying.com/)完成声音和动态剪辑。

想让平台先组织剧本和故事板，可以从 [小云雀](https://xyq.jianying.com/)及其 [官方手册](https://xyq.jianying.com/tutorials/web-manual)开始，再自己审核和终剪。

需要人物表演时，再从 [即梦](https://jimeng.jianying.com/)、[可灵中文入口](https://klingai.kuaishou.com/)、[Vidu 中国站](https://www.vidu.cn/)、[海螺国内入口](https://hailuoai.com/video/create)选择一个主视频工具。不要先同时买齐工具。

资料核对截至 2026-10-25，具体能力、费用、地区和账号权限以实际产品为准。网站引用不代表本项目已完成 API 对接；商业平台可直接使用，fork 则另需开源代码与许可证。

## 第一轮只检查三个问题

1. 每次姓名出现都读对，声音没有串角色。
2. 角色、衣服、道具与动作可接受，整段播放没有漏检中间瑕疵。
3. 画面、台词和分镜确实表达了批准的剧情。

把结果和返工原因记录下来，再扩展镜头、人物和集数。完整导航见 [个人创作指南](creator-guide/README.md)。

## 进阶工程工具是可选项

已有离线 CLI、结构化剧本与审核工具继续保留给需要批量检查和本地记录的作者。选择使用时再读 [工程架构](architecture.md)和 [数据契约](data-contract.md)。mock 演示仍是模拟，静态检查通过也不证明真实生成质量；不要把这些高级选项当成开始制作的门槛。
