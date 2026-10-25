# 本地自动化与制作包

`creator` 是本项目已经实现的本地辅助入口：查工具与线路、创建可编辑样例、检查台词与引用、导出制作参考包。它不登录网页、不上传参考、不提交生成任务、不调用付费 API，也不自动发布。

可以完全按 [手工工作流](02-workflow.md)创作；只有希望减少重复整理时，才使用本页命令。核心需要 Python 3.10 或更新版本，以下命令在仓库根目录运行。Windows 按安装情况可把 `python` 换成 `py`。

## 一次跑通的命令

```bash
python -m manju creator tools
python -m manju creator routes
python -m manju creator new --route motion_comic --title "我的第一条漫剧" --out build/first-film
python -m manju creator check build/first-film
python -m manju creator pack build/first-film --out build/first-film-pack-v1
python -m manju creator verify-pack build/first-film-pack-v1
```

`new` 复制的是原创《雨夜来信》样例：默认 6 个镜头、计划 46 秒、两名角色、一个场景。`--title` **只设置项目标题，不会把示例故事自动改写为你的作品**。第一次可以先原样检查和导出；制作自己的内容时，请一起替换下述四份输入。

`new` 和 `pack` 都不覆盖已经存在的目录。重复试跑用新目录，例如 `build/first-film-v2`、`build/first-film-pack-v2`。

## 查看工具与选择线路

```bash
python -m manju creator tools --stage audio
python -m manju creator tools --stage video --json
python -m manju creator routes --json
```

`tools` 读取仓库已登记的工具目录、官方地址和核对日期，不会进行联网搜索或刷新当前价格。`--stage` 可选 `script`、`reference`、`image`、`video`、`audio`、`edit`、`review`、`manage`、`publish`。

三条线路 ID 固定为：

- `motion_comic`：图片动态漫，图片、声音与剪映动态化为主。
- `story_video`：逐镜视频短剧，参考图到视频，再筛片和终剪。
- `agent_first`：小云雀等一站式 Agent 起稿，自己确认资产、片段和成片。

例如需要视频线路时，使用新的输出目录：

```bash
python -m manju creator new --route story_video --title "我的剧情短片" --out build/story-film
```

线路的输入、输出、工具和人工检查点见 [工作流](02-workflow.md)。工具链接存在不代表 API 已接通，费用和账户权限仍在实际产品中核对。

## 编辑四份输入

创建目录还包含 `project.json`，用于记录项目标题、线路和格式版本。日常创作主要编辑以下四份文件；建议用文本编辑器处理 Markdown，用 WPS 或其他表格软件编辑并保存 UTF-8 CSV。

### script.md 原剧本与台词索引

保留完整故事和必须传达的事实。自动检查读取独立的台词索引行，例如：

```text
L001 | C001 | 乐知夏，这封信是你放的？
L002 | C002 | 单于宁，先别拆。
```

每个 `L` 编号是一个台词 ID，`C` 编号指向说话人。镜头表中的原文和说话人必须逐字匹配，所有索引台词按原顺序恰好分配一次。换行或自然段中的剧情仍由本人核对，程序不会自动理解故事因果。

### characters.md 人物与场景

使用可识别的标题登记角色和场景：

```text
## C001 单于宁
人物外观、服装、声音方向与禁改项。

## C002 乐知夏
另一位人物设定。

## SC001 深夜档案室
场景、光线、人物位置和关键道具。
```

不要只改姓名而忘记词典和台词。角色和场景 ID 尽量保持稳定；这些 ID 是本地引用，不会自动变成平台的角色 ID。

### pronunciation.csv 读音表

表头必须保持：

```csv
term,pinyin,note
```

为每位角色登记完整姓名及自己确认的数字声调拼音，例如 `chan2 yu2 ning2`。另可登记称呼、地名和术语。`note` 保存读音与试听说明。

检查器只检查词典结构、数字声调格式与姓名登记，不证明拼音音节、姓氏读法或实际声音正确。完整姓名、称呼和句中读音仍需试听。

### shots.csv 分镜表

表头必须保持以下顺序：

```csv
shot_id,scene_id,character_ids,line_id,speaker_id,dialogue,visual,duration_seconds,image_prompt,video_prompt
```

| 字段 | 填写方法 |
| --- | --- |
| `shot_id` | 稳定的镜头编号，例如 `S001`，不填写文件路径 |
| `scene_id` | 已在人物与场景文件登记的场景，例如 `SC001` |
| `character_ids` | 画面中可见角色，多个用英文分号分隔，如 `C001;C002`；无人镜头可留空 |
| `line_id` | 本镜头对应的原台词编号；无台词则留空 |
| `speaker_id` | 原台词说话人；无台词时留空 |
| `dialogue` | 原台词逐字复制；无台词时留空 |
| `visual` | 画面、主要动作和必须传达的信息，不能留空 |
| `duration_seconds` | 计划秒数，正数，最多三位小数；不是配音实测值 |
| `image_prompt` | 本镜头图片或参考图提示词，不能留空 |
| `video_prompt` | 视频／动态化提示词；视频与 Agent 线路必填，图片动态漫可留空 |

**允许画外音。**`character_ids` 表示画面角色，不要求 `speaker_id` 一定出现在其中。默认样例 S004 是信封特写，画面只登记 C001，C002 在画外说话；不要为了通过检查把不存在的人物加进画面。

CSV 含英文逗号、引号或换行时，用表格软件正确导出 CSV，避免手工拆列造成列数错误。

## 检查通过代表什么

```bash
python -m manju creator check build/first-film
python -m manju creator check build/first-film --json
```

检查范围包括人物与场景引用、镜头编号、台词原文与说话人、顺序、完整姓名词典及计划时长等结构条件。通过后可以导出参考包。

它不判断参考图是否正确、声音是否读对、生成视频是否符合剧情，也不证明费用或使用权限。媒体质量仍按 [质量检查](03-quality-and-repair.md)执行。

## 制作包里有什么

```bash
python -m manju creator pack build/first-film --out build/first-film-pack-v1
```

制作包必须放在原项目目录之外，不能输出到 `build/first-film/pack` 之类的子目录。包内保存冻结的参考和模板，原项目仍是下一轮编辑入口。

- **`inputs/`**：项目配置及四份输入的快照，记录本包使用的原文、设定、词典和镜头表。
- **`README.md`**：本线路的逐步操作、输入输出、人工检查点、回退方式及官方工具链接。
- **`tools.snapshot.json`、`routes.snapshot.json`**：工具目录和线路目录快照，保留来源核对日期。
- **`shots/S001.md` 等**：逐镜制作卡，含画面任务、图像与视频提示词、原台词、独立读音提示和三类检查点。
- **`prompt-library/`**：四份参考图、图生视频、Agent 交接和连续性检查模板。它们是模板副本，实际应用仍需填入自己的素材和要求。
- **`tts-lines.csv`**：逐句原文和 `pronunciation_hints` 独立列。朗读正文使用原文或经过试听确认的声音输入，不把拼音说明一起念出。
- **`subtitles.planned.srt`**：按计划镜头时长分配的字幕草稿，**尚未按实际音频或终剪测量**，不能直接标记为最终字幕。
- **`review.csv`**：每镜头的姓名读音、画面和剧情检查全部为 `pending`，等待本人实际试听和观看。
- **`attempts.csv`**：只有表头的空尝试表，用于记录实际工具、模型、参考版本、候选、费用和原因。
- **`index.html`**：本地浏览入口，汇总镜头和官方工具地址。
- **`manifest.json`**：制作包文件摘要与 `planning_only` 状态，用于冻结完整性检查。

默认导出时没有真实图片、声音或视频。打开 `index.html` 或制作卡，再进入官方工具生成；参考图和原文仍需自己按平台要求主动上传。

## 冻结包与自己的工作记录分开

```bash
python -m manju creator verify-pack build/first-film-pack-v1
```

`verify-pack` 检查清单与文件摘要是否匹配，并拒绝缺文件、改动或额外未登记文件。**它只证明冻结包完整，不证明媒体正确、人审已完成或素材可商用。**

开始实际创作前，手动把 `review.csv` 和 `attempts.csv` 复制到自己的工作记录目录，例如 `build/first-film-records/`，在那里填写。平台导出的媒体、选片记录和剪辑工程也放在自己的工作目录，不写进冻结参考包。

如果直接改了包内审核表，校验失败是预期行为。不要靠篡改清单把它重新标成完整；回到自己的工作副本记录结果。修改原项目后，先 `check`，再导出 `first-film-pack-v2`，保留旧包对应关系。

记录字段及审片卡见 [制作记录](04-production-records.md)和 [质量检查](03-quality-and-repair.md)。

## 三层自动化边界

**第一层 网页内制作。**在即梦、可灵、Vidu、海螺、小云雀、讯飞和剪映中完成真实生成、试听、选片与终剪。个人网页操作可先独立跑通，不以写代码为前置。

**第二层 当前本地自动化。**本项目确定性生成目录、官方链接、制作卡、台词清单、字幕草稿和待审核表，检查引用并冻结版本。它减少整理工作，但没有控制那些网站。

**第三层 后续接口或开源工作流。**当真实重复操作已经明确时，再接供应商公开 API 或固定版本的 ComfyUI 工作流。需要单独实现准入、费用、任务 ID、超时查询、取消、结果归档及凭据保管；复用或 fork 平台还要核对开源许可证、节点和模型许可。不能把本页命令当作已完成这些接入。

下一次制作先沿用已经可用的生成线路，再按实际返工和搬运成本决定扩展哪一层。
