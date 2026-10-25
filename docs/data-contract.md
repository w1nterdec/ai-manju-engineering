# 数据契约 0.1

> 本页属于可选工程参考。个人实际制作先读[创作指南](creator-guide/README.md)；原有 mock 或接口契约不表示真实平台已接通。

当前使用 UTF-8 JSON，不接受重复键、NaN 或 Infinity。不要求安装 JSON Schema 库；`manju.validation.validate` 是本版本可执行的契约依据。字段按严格集合检查，未知字段会报错，避免拼写错误被忽略。未来契约升级需要迁移程序和兼容测试。

## 独立单集

完整例子是 `examples/midnight_letter/episode.json`。顶层必需字段：`schema_version`、`project`、`characters`、`pronunciation_lexicon`、`beats`、`initial_state`、`shots`。

- `schema_version`：固定字符串 `0.1`。
- `project`：`id`、`title`、`language`、`aspect_ratio`、`visual_style`、`canon_facts`、`negative_prompt`。可选 `dialogue_cps_warning` 为正数，默认 6 字符/秒，仅作计划时长预警。
- `characters[]`：`id`、`name`、`appearance`、`voice_direction`，可选 `reference_image` 为路径备注。当前不自动加载或验证参考图文件。旁白也登记一个角色，并使用 `voiceover`。
- `pronunciation_lexicon[]`：`term`、`pinyin`、`note`。完整角色名必须登记；拼音仅校验数字声调格式，不自动验证音节或判断姓名读法正确。
- `beats[]`：`id`、`summary`、非空 `required_facts`、`lines`。`lines` 可以为空，以表达纯动作剧情。
- 原始 `lines[]`：`id`、`speaker_id`、`text`；可选 `speech_text`。配音默认采用原文，字幕始终采用原文。
- `initial_state`：非空字符串键值对象。各镜头前后状态必须保存同样的键集合，避免拼写错误增加“新道具”。
- `shots[]`：`id`、非空 `beat_ids`、`duration_ms`、`location`、`time`、`character_ids`、`framing`、`action`、`emotion`、`state_before`、`state_after`、`lines`。
- 镜头中的 `lines[]`：`line_id`、`delivery`、`start_ms`、`end_ms`。时间为相对镜头开始的整数毫秒，须满足 `0 <= start < end <= duration`。`delivery` 为 `on_screen`、`off_screen` 或 `voiceover`。

ID 须为大写字母开头的 `A-Z`、`0-9`、下划线，最长 64 字符。角色、节拍、台词、镜头各自在本集内部唯一。人物完整姓名和词典 term 也不得重复。

每个原剧本节拍至少被一个镜头覆盖；每句原台词恰好分配一次，且维持原剧本顺序。单镜头可以覆盖相邻多个节拍，但不能引用不属于该节拍的台词。当前单字幕轨不支持多人同时对白；闪回需显式写在原剧本顺序里。部分遮挡人物是否算画面内角色由作者决定，关键是与实际制作保持一致。

## 共享设定与系列

使用共享设定时，单集顶层仅包含 `schema_version`、`canon_ref`、`project`、`beats`、`initial_state`、`shots`。`canon_ref` 相对单集文件解析；不要加载不可信来源提供的项目文件。

共享单集的 `project` 仅可设 `id`、`title`、可选 `dialogue_cps_warning`。`canon.json` 保存 `canon_version: "0.1"`、共享 `project`、`characters`、`pronunciation_lexicon`。共享 `project` 仅含语言、画幅、风格、世界事实与负面制作约束，禁止单集静默覆盖。

系列清单包含 `series_version: "0.1"`、非空 `id`、布尔值 `continuous`、非空 `episodes` 路径数组。单集路径须位于系列清单目录内；系列检查要求各集均使用共享设定，且共享内容摘要一致。`continuous: true` 要求下一集初始状态等于上一集结束状态。跳时、换装等先显式加入转场镜头，或为不连续系列设为 false；后续将扩展具名状态迁移。

## 输出与错误码

`manifest.json` 中 `status: planning_only` 永不因人工复核命令自动改成已发布；`tasks.json` 仅为计划。`input_hashes` 对剧本与可选共享设定分别做 SHA-256；`files` 记录冻结计划文件摘要。`template_sha256` 记录编译模板，不证明模型端实际采用了模板。

- E001：字段、类型、版本或格式错误。
- E002：重复 ID、姓名、术语或数组项。
- E003：角色姓名未登记读音。
- E004：不存在的角色、节拍或台词引用。
- E005：节拍或台词顺序偏离原剧本。
- E006：状态键不一致或镜头状态断链。
- E007：台词与镜头节拍归属不匹配。
- E008：画面内说话人未出场。
- E009：对白时间越界、重叠或倒序。
- E010：剧情节拍或台词遗漏。
- W001：缺少参考图备注；W002：配音与字幕不同；W003：计划语速偏快。
- S001：系列契约、共享设定或跨集连续性错误；G001：构建完整性或人工复核记录不满足要求。

CLI 退出码：0 为所请求范围通过，1 为检查未通过，2 为文件、JSON 或命令执行错误。`check`、`check-series`、`gate` 支持 `--json`。读取失败也输出 `passed: false`，便于 CI 使用。
