# 雨夜来信 个人创作者原创样例

这是可直接照着制作的 46 秒、6 镜头、2 名成年角色、1 个场景的小样，重点练习姓名读音、人物与道具一致性，以及原剧本与分镜对应。没有附带生成图片、配音或视频，不能作为已制作成片。

## 文件怎么用

- [script.md](script.md)：故事、剧情事实与唯一台词索引。改台词时先改这里，再同步分镜。
- [characters.md](characters.md)：角色、固定服装、音色方向、场景与道具状态。
- [pronunciation.csv](pronunciation.csv)：作者为本例确认的目标读音，字幕保留正确汉字。
- [shots.csv](shots.csv)：逐镜画面、台词引用、计划时长与可复制图像／视频提示词。

## 第一次制作

1. 先读剧本和角色，选一种画风。建议从原创中文 2D 悬疑漫画开始，固定竖屏 9:16。
2. 在[即梦](https://jimeng.jianying.com/)等所选生图工具制作角色和场景参考，按[参考图模板](../../prompts/07-reference-and-keyframes.md)确认后再做镜头图。
3. 在[讯飞智作](https://peiyin.xunfei.cn/)、剪映文本朗读或自己的录音中，先听两个完整姓名的小样，再逐句配音。姓名的控制写法以工具实际支持为准。
4. 用镜头图加临时配音在[剪映](https://www.jianying.com/)做预览。要走动态漫画路线，可以直接用关键帧推拉和停顿；不必把六个镜头都生成视频。
5. 需要人物动作时，将选用关键图和 shots.csv 对应的 video_prompt 交给[即梦](https://jimeng.jianying.com/)、[可灵](https://klingai.kuaishou.com/)、[Vidu](https://www.vidu.cn/)或[海螺](https://hailuoai.com/video/create)中的一个主工具。实际时长选项不足时，重新拆镜或剪辑，不能把计划秒数当作模型保证。
6. 也可以按[Agent 交接模板](../../prompts/09-agent-handoff.md)将剧本和资料交给[小云雀](https://xyq.jianying.com/)，逐步确认人物、场景和故事板，记录与样例分镜不同的地方。
7. 按[连续性模板](../../prompts/10-continuity-check.md)完成实际媒体复核，再制作字幕、后期日期叠字和成片。

## 本例最需要检查的地方

- 单于宁的姓名读 `chan2 yu2 ning2`，乐知夏读 `yue4 zhi1 xia4`。这是本角色设定，不能据此推断其他同名人的读音。
- 只有一个牛皮纸信封；从桌面到单于宁右手后，后续镜头不换手、不增加信封、不拆封。
- 单于宁画左、乐知夏画右；门在后墙中央，始终关闭，不出现门外人物。
- 信封上的日期由后期准确叠加为 `2026年10月26日`。不依赖模型生成的文字承担关键剧情。
- 台词恰好使用一次，顺序与 script.md 保持一致。配音纠音替换不进入字幕。

## 可选的本地资料自动化

如果希望少复制文件，可在仓库根目录执行：

```bash
python -m manju creator new --route motion_comic --out build/my-first-film
python -m manju creator check build/my-first-film
python -m manju creator pack build/my-first-film --out build/my-first-film-pack
```

`new` 默认以本例准备一套个人项目资料，也可用 `--title` 指定项目名。`check` 检查台词、镜头和资料引用；`pack` 输出供外部工具操作的制作包。它们不调用云生成、不产生真实图像或声音，也不能替代试听和审片。输出目录换新名字，避免覆盖已有版本。

## CSV 的约定

shots.csv 表头为 `shot_id,scene_id,character_ids,line_id,speaker_id,dialogue,visual,duration_seconds,image_prompt,video_prompt`。`character_ids` 用分号分隔；纯动作镜头的台词三列留空；初版每镜头最多一句台词。剧本中的索引格式为 `L001 | C001 | 台词原文`，它是台词来源。

pronunciation.csv 表头为 `term,pinyin,note`。`duration_seconds` 是计划时长，正式剪辑需按实际配音与可用画面调整。CSV 内容是操作资料，不是任意模型 API 的请求参数。

替换成自己的作品时，保留镜头和台词编号，先改故事与固定设定，再更新提示词。项目首页的个人工作流命令可帮助准备资料；整个样例也能完全手工使用。
