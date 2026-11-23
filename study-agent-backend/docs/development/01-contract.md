# 共用开发契约

契约版本 **1.0**。此页约定应用、网页、工作流怎样交接。首批基准数据在 [examples.json](examples.json)。正式接口以此页为准，样例用于联调和验收。

## 对象和引用

应用 ID 为不透明字符串。长期引用一律带整数 `revision`，从 1 开始。同一对象正文变更后产生新版本。时间用 UTC ISO 8601，展示时按用户当地时间换算。教学文本可用 Markdown。

| 对象 | 主要字段 | 行为 |
| --- | --- | --- |
| 学习图 | `id, mode, title, goal, origin_ref?, status` | `mode` 为 `textbook` 或 `goal`，表示从什么入口开始。`status` 为 `preparing/sparse/ready`，分别表示首条路线准备中、可探索、已有正式路线。从目标开始的原图可以进入 ready，并保留探索内容。 |
| 学习节点 | `id, graph_id, revision, kind, title, objectives, reading, activities, source_refs` | `kind` 为 `mainline/branch/predicted/exam/summary`。前三个是学习节点来源，后两个是整理和自测用途。灰色候选是尚未采纳的建议，采纳后产生正式学习节点。可在正式路线中加入等价的旧节点。 |
| 学习目标 | `id, text` | 一条可以观察的学习要求，例如「能用 TTL 判断缓存条目是否已过期」。目标请求与证据可通过节点版本和目标 ID 精确对齐。 |
| 阅读安排 | `intro_md, steps, key_points, source_refs` | 主线和预备候选带实际学习材料入口。步骤可短到一两段。临时支线按原问题先起步，内容可随问答补充。 |
| 路线与关系 | `id, revision, graph_id, kind, title, node_ids, counted_node_ids, edges` | `kind` 为 `full/core/limited`。顺序由 `node_ids` 表达。关系由边单独表达，`kind` 为 `prerequisite/related`，前者必有方向和理由且无环。章节可自由起步，路线推荐顺序只负责导航。 |
| 学习记录 | `id, graph_id, node_id, revision, kind, body_md, refs, created_at` | 类型至少有 `note/question/answer/explanation/exercise/feedback/branch_summary/merge_summary/exam_review`。正文归提交当时的焦点。修改后的正文、反馈和跨节点引用可分别回查。 |
| 节点完成 | `node_id, marked_at` | 每位学习者每个节点一份可取消的标记。相同节点在各路线共用此标记。 |
| 掌握证据 | `id, target_node_ref, objective_id, record_ref, independence, demonstrated, assessment_md` | `independence` 为 `unaided/with_reference/with_hint`。`demonstrated` 写实际展示的能力，例如执行、解释、迁移或回忆。可以引用其他节点的独立表现。已有提示后的修订记录在反馈状态，独立掌握仍待新证据。 |
| 候选 | `id, graph_id, parent_candidate_id?, anchor_node_id?, based_on_refs, preparation, reason_md, source_refs, recommended, status` | `status` 为 `proposed/adopted/dismissed`。准备内容含标题、目标、引入、阅读步骤、知识点、活动。被采纳时可返回对应正式 `node_id`。 |
| 里程碑 | `id, graph_id, revision, outcome, status, evidence_refs` | `status` 为 `active/achieved`。阶段产出可链接当时的实际作品和记录。Teacher 可建议，用户决定。 |
| 同步状态 | `focus, ready_routes, recent_jobs` | 只有一个当前焦点。浏览位置由网页独立维护。多个标签页从 API 读最新的焦点、版本和自测锁。 |

路线成员资格由发布的路线记录决定。一个过去从候选采纳的节点可以同时是教材路线成员。应用用成员资格、当前学习方式和支线关系共同决定主线或探索的推荐规则。

### 引用对象

`Ref = { kind, id, revision, locator? }`。支持 `source/node/route/record/exam_item`。读取接口按版本命中原件或其冻结快照。已上传教材可同时展示带页定位的原文件和当时选用的摘录。网页来源保存 URL、取用时间、标题、相关摘录及可得的章节。精确版本缺失时返回明确原因。

- PDF 页定位用 `locator.page`，从文件物理第一页算 1，另可附 `label` 或 `section` 供人阅读。Markdown、文本和网页用 `section`，提取时有行号可加 `line_start,line_end`。
- 记录定位可用 `locator.quote` 和可选 `start,end`。若暂不做范围高亮，仍须打开该版正文并显示对应引文。模型产出的引用只能指向应用随本次请求提供或经本次工具读取登记的版本和范围。
- 节点引用可用 `locator.activity_id` 指向该节点版本的过关活动。
- 比赛演示样例用自编短教材和示例记录。正式计划对教材原节、教材口径、补充来源、勘误分别保留可核查的来源或说明。

每一条过关活动含 `id, kind, objective_ids, prompt_md, source_refs`，准备结果另含 `solution_md`，供预备检查和需要时讲解。活动作答作为 `exercise` 记录，`refs` 给活动所在节点版及具体题目标识。

## 焦点、记录与学习状态

- 焦点形如 `{ graph_id, node_id, revision, checkpoint, lock }`。版本号随切换或锁状态变化而增。断点保存可用的段落、当前问题或上次学习位置。`lock` 为空或 `{ kind: "exam", attempt_id }`。首次尚未学习时焦点可空，初次正式进入以空版本比较写入。
- 每个学习节点可为该用户保留最近断点。普通断点保存校验同一焦点版本，焦点版本只标识切换和锁定。版本有效时，恢复原处仍优先用该次支线记录的出发断点。打开另一节点的浏览位置单独由前端管理。
- 浏览另一个节点只取资料。发问、提交草稿、过关题等动作带预期焦点版本，另带明确的资料引用。浏览 B 时仍可把问题记在 A 并引用 B。开始在 B 学习要用显式 `focus/start` 动作。
- 开支线时写入来源节点、出发断点、原问题或原因的引用，并切焦到新支线。返回时应用先恢复原焦点及断点，再排续学任务。续学只使用从这一支线选取的内容和原问题，引用可回查。任务失败时，用户可在已恢复的焦点重试同一上下文。
- 手动合并由用户选记录及其版本，可追加到现有目标节点或创建阶段整理节点。整理的原始输入各自保留，汇总结果有独立记录及出处。手动合并保留当前焦点，用户可随后显式切换。支线返回的自动 merge 只接续教学上下文。两种 merge 都保留来源、完成标记及证据关系。
- 每个学习表达区分最新草稿与用于学习判断的已保存版本。笔记持续保存，用户写完整可做 `finish_expression`。Teacher 反馈按 `target_record_ref` 指向被核查的正文版本。修订后的新版本可再次核查。每条反馈含 `category, severity, anchor_quote?, hint_md, refs`。类别至少有 `supplement/misunderstanding/error`，严重程度可用 `low/medium/high`，同一表达可有多类问题。被提示后修正的状态单独保存。
- 已发布的全面路线、核心路线、限时路线分别计算 `completed_count / counted_count`，各自统计。目标准备区呈现里程碑与阶段产出。同一活动的证据可支持明确的目标，证据可回查原版。
- 唯一强制复习条件是用户跳过某个真实必要且未完成的前置后，在后继节点至少两次表现出由该前置缺失导致的同一类困难。Teacher 给出对应证据和前置方向，应用核对边、完成状态、两次记录及焦点可切条件后记录原因并执行回到前置。保留后继节点断点，方便复习后返回。普通缺口、已完成前置或证据不足时以解释和建议处理。正常开节点无课程锁，计时自测的焦点锁单独处理。

## 两个入口和路线发布

| 输入或操作 | 应用输出与权限 |
| --- | --- |
| 导入教材 | 建立或选择图，选择系统学习或限时/备考目标。收集范围、目标、时间、章节或考试资料。缺省全书范围。后台解析、分组分析、编排、验收，待结果合格后事务性开放完整可用的正式路线。 |
| 时间或考试要求 | 留出至少 7 天时可安排独立的限时路线。结合用户提供的考查范围、重点和样题优先安排，资料不足时以教材基础为有注明的参考。少于 7 天返回优先清单、资源和说明，保留问答。 |
| 只输入目标 | 先备一个可观察的里程碑，查找并留存实用可靠来源，备好几个可连续学习的候选。准备好后用户选择要采纳的候选。前端显示理由、来源、关系和可读的「建议」状态。 |
| 主线答疑与支线 | 教材主线内在本节点解释、提示或练习。用户主动开支线后，可在局部目标内请求后续建议。新目标已需要系统学习时应建议新图，并在用户选建时保留起因与原节点链接。 |
| 改路线或为目标图补教材 | Teacher 给出修订建议或合并映射，用户查看并确认后应用。等价节点保留 ID 与完成状态，新增目标另备学习内容，证据只按实际展示的目标使用。保留旧路线、旧节点版本和可回查教材来源。 |

后台任务为 `{ id, kind, status, stage, result?, error?, updated_at }`。`status` 为 `queued/running/succeeded/needs_source/failed`。常用 `stage` 为 `parse/analyze/assemble/verify/publish`，其它任务带可展示的实际阶段。浏览器退出后任务仍可继续。验证失败或请求补件时，旧有可用图和路线可照常使用。

| 准备任务成功的情形 | `result` |
| --- | --- |
| 发布完整或限时路线 | `{ kind: "published_routes", graph_id, route_refs }` |
| 原图加教材或修订，等用户采纳 | `{ kind: "route_proposal", graph_id, suggestion_id, base_route_ref?, preview }`。预览展示复用、扩展、新增及范围检查。 |
| 不足一周的限时清单 | `{ kind: "study_checklist", graph_id, items, note_md }`。每项含标题、建议理由和来源。 |
| 目标入口准备完成 | `{ kind: "goal_prepared", graph_id, milestone_id, candidate_ids }` |

## HTTP 约定

路径以 `/api/v1` 开头。JSON 成功为 `{ "data": ... }`，错误为 `{ "error": { "code": "...", "message": "...", "details": {} } }`。流式下载用对应内容类型。涉及学习记录或会话状态的写入带 `Idempotency-Key`，例如客户端为本次点击生成 UUID，网络重试复用原键。同用户、同路由及同键的不同载荷返回 409。焦点和当前草稿写入另作版本校验。

| 方法及路径 | 输入要点 | `data` 要点 |
| --- | --- | --- |
| GET `/workspace` | 可选查询 `graph_id, node_id` 表示浏览 | `focus, graphs, graph?, node?, routes, jobs, candidates, milestones, completions, route_progress`。带浏览参数时追加该节点及其学习材料索引。导入草稿只返回任务状态。每条进度有 `route_id, completed_count, counted_count`。 |
| POST `/graphs` | `mode, title, goal, origin_ref?` | 新图和下一步。可重复回到稍后继续填写的图。 |
| POST `/graphs/:id/sources` | multipart `file`，可选 `purpose` 为 `textbook/assessment/supplement` | `source_ref` 与解析状态。每文件独立上传。 |
| POST `/graphs/:id/plans` | `intent, source_refs, scope?, days_available?, assessment_md?, base_route_ref?`。`intent` 为 `full/limited/goal/add_textbook/revise`。已有路线的修订带基准引用。 | 202 与任务。目标入口可传空材料列表，学习目标来自学习图。 |
| GET `/jobs/:id` / POST `/jobs/:id/retry` | retry 可补 `source_refs` | 任务及阶段，或新任务 ID。重放已成功任务回原结果。 |
| POST `/focus/start` | `node_id, expected_focus_revision, checkpoint?` | `focus` 和起步所用的节点版本。 |
| PATCH `/focus/checkpoint` | `checkpoint, expected_focus_revision` | 更新的 `focus`。仅保存当前焦点的合法学习位置。 |
| POST `/branches` | `expected_focus_revision, title, question_md, origin_refs, checkpoint` | 新 `branch`、来源关系及已切换的 `focus`。 |
| POST `/branches/:id/return` | `expected_focus_revision` | 恢复的 `focus`、`return_event_id`、续学 `job_id`。该支线可保留供之后回访。 |
| POST `/graphs/:id/merges` | `record_refs, target_node_id?, new_title?`，指定一种去向 | 整理任务及目标。结果含 `summary_ref` 和用于阅读的原始引用。 |
| PUT `/nodes/:id/completion` | `completed` | 节点的完成标记和受影响的路线计数。 |
| POST `/nodes/:id/records` / PATCH `/records/:id` | `kind, body_md, refs, action, expected_focus_revision`。更新带 `base_revision`。`action` 为 `save_draft/save/finish_expression` | 当前版本 `record_ref`，正文提交触发时可附 `job_id`。 |
| POST `/teacher/messages` | `message_md, expected_focus_revision, refs, intent?`。意图可为 `ask/check/practice/suggest_next` | 提问 `record_ref`，答复 `job_id`。最终由任务回教学记录、引用及可用的反馈或建议。`intent` 可帮助路由，实际教学策略由 teacher 决定。 |
| GET `/nodes/:id/records` | 可选 `cursor` | 分页的教学、活动及记录索引，含证据、合并和支线返回事件链接。 |
| GET `/refs` | `kind,id,revision`，定位参数按引用类型 | 该版本的内容、可用定位及附件入口。阅卷和开考规则对全部读取路径生效。 |
| GET `/nodes/:id/related` | 可选 `after` 用来增量查询 | keeper 提示、解释与引用，含 `suggested/retracted/dismissed` 状态。 |
| POST `/suggestions/:id/decisions` | `decision` 为 `adopt/dismiss`，路线修订接受时带 `base_revision` | 采纳结果。候选生成正式节点及映射，路线变更提交新版本，关联提示可关闭。 |
| PATCH `/milestones/:id` | `base_revision, outcome?, status?, evidence_refs?` | 更新后的里程碑。 |
| GET `/exports/markdown` | `graph_id`，可选 `node_id` | UTF-8 Markdown 下载，包含选定范围内的用户笔记、已保存表达和必要出处。 |

以后台任务为主要结果的操作使用 202。同步新建对象可返回 201 并附后续任务 ID。常用校验失败使用 422 `INVALID_INPUT`。409 可用 `FOCUS_CHANGED/EXAM_LOCKED/REVISION_CONFLICT/IDEMPOTENCY_CONFLICT/ATTEMPT_CLOSED`。无效或不可见的引用使用 404 `REF_UNAVAILABLE`，待补材料的任务给出 `NEEDS_SOURCE` 以及缺失范围。结果只在学习者可以访问的图和记录下读取。前端遇版本冲突刷新当前状态，保留用户未提交的文本。

## 自测 API 与约束

| 方法及路径 | 输入要点 | `data` 要点 |
| --- | --- | --- |
| GET `/exams/:node_id/preview` | 节点 ID | `duration_seconds, allowed_materials, objectives, rules_md, preview_revision`。有当前场次时附状态和进入入口。 |
| PATCH `/exams/:node_id/preview` | `base_revision, requested_rules_md` 填希望商议的开卷条件或时长 | 复核任务。完成后生成新预览版及可用条件。 |
| POST `/exams/:node_id/start` | `confirmed: true, preview_revision, expected_focus_revision` | 当前场次 `attempt`、试题、服务端时间和锁定焦点。只能由最终确认发起。 |
| GET `/attempts/:id` | 场次 ID | 状态、当时允许显示的试题和勘误、当前答题版本或正式答卷链接。运行中返回 `server_time` 和 `deadline_at`。 |
| PUT `/attempts/:id/answers/:item_id` | `body_md, base_revision` | 已保存的答题版本。独立校验截止时间、题目归属和版本。 |
| POST `/attempts/:id/reports` | `item_id, concern_md` | 已接收，供 teacher 优先复核。 |
| POST `/attempts/:id/submit` | `confirmed: true` | 终态 `attempt`、正式答卷引用和复盘入口。 |
| POST `/attempts/:id/reviews` | `expected_focus_revision, message_md?, refs?` | 考后复盘任务或已有复盘记录。考试节点保持焦点，能显式引用相关知识节点。 |

考前预览、节点数据、素材查询与导出均隐藏本场试题和解析。场次持有自己的 `question_set_revision, started_at, deadline_at, status`。`status` 为 `active/submitted/expired`。计时期间仅开放本场允许的资料、规则问答、作答和题目报告。Teacher 可在后台复核，题目对用户可见的变更只有确认的勘误、作废及理由。到点以服务端事务锁冻结已持久化答卷，即使没有页面在线。终态保留原交卷版本和时间线，独立的复盘记录和复测证据另写。

## 应用与 AgentArts 的调用

比赛版发布以下两种工作流。应用向 provider 传共用请求。AgentArts 适配器按已部署流程的官方调用示例，在开始节点的 `payload_json` 输入该对象序列化的字符串。结束节点返回 `result_json` 字符串。应用测试可从同契约 mock 返回结果。

```json
{
  "schema_version": "1.0",
  "workflow": "resume_branch",
  "request_id": "req_resume_01",
  "input": {}
}
```

输出统一为 `{ schema_version, workflow, request_id, outcome, result, issues }`。`outcome` 为 `ok/needs_source/failed`。成功填 `result`，非成功以 `issues` 给范围、可改正问题和说明。请求及结果范例均在 [examples.json](examples.json)。

| 工作流 | 核心输入 | 必验输出 |
| --- | --- | --- |
| `textbook_plan` | `goal, intent, scope, sections, assessment_refs, existing_nodes, source_catalog`。材料片段带原始定位。长教材可提前按目录分析并用同版本阶段结果汇编。 | 单元节点草案、目标/阅读/活动、路线顺序和真实前置、节到节点的覆盖、题目到目标的映射、复用建议和验收问题。使用请求提供的章节和来源，计划内临时节点 ID 由应用在发布时映射。 |
| `resume_branch` | `focus, focus_node, origin_question, branch_records, allowed_refs`。附与此次接续有关的支线正文版本和原文。 | `reply_md, used_refs, next_step_md`。答复接到原问题，`used_refs` 精确引用本次实际采用材料。 |

应用锁定工作输入的版本，解析并检查结构、引用集合、归属与业务关系后再写入。超时可重试，同一次操作最多发布一份结果。浏览器侧通过任务和引用读取结果。平台调用可参照 [AgentArts 工作流 API 调用](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0055.html)和[发布工作流的输入参数](https://support.huaweicloud.com/bestpractice-agentarts/agentarts_06_0022.html)。

## 其他教学操作的最小返回

这些操作使用可配置的教学服务。应用传事件版本、焦点与目标、允许引用的原文及明确的操作意图。首版按下表先接通稳定业务字段。

Teacher 与 keeper 共用学习记录检索及版本读取。Teacher 的公开搜索和来源核对也由应用工具提供。工具名称、参数、可用场景与负责方见[工具契约](06-agent-tools.md)。

| 操作 | 教学服务返回并由应用核对 |
| --- | --- |
| 普通问答与核查 | `reply_md, used_refs, feedback, evidence, suggestions`。可无核查或证据。反馈项给 `target_record_ref, category, severity, anchor_quote, hint_md, explanation_md?, refs`。证据只指真实表现和存在的目标。应用写入后，任务返回 `record_ref, used_refs, feedback_refs, evidence_ids, suggestion_ids`，相应列表可以为空。 |
| 关联与回看 | `target_node_ref, source_ref, relation_kind, reason_md`。关系可用 `prerequisite/analogy/related`。应用补提示 ID 与状态。Teacher 复核按提示 ID 提出可选的 `correction_md`，应用校验当时的节点和出处。 |
| 目标与候选 | `milestone, candidates, source_catalog`。Teacher 的搜索结果需要可访问的来源或其保存摘录，待核实材料显式标明。候选引用已确认的来源与现有记录，应用保存后才允许被采纳。 |
| 整理、修订和回学 | merge 返回 `summary_md, used_refs`。路线计划给基准及采用预览。回学建议含目标前置、两次记录版本及原因。三者均由应用决定写入与是否符合切焦条件。 |
| 考中复核 | 只读当场题目版本和用户报告。输出 `item_id, checked_revision, disposition, reason_md, corrected_prompt_md?`，处理状态为 `keep/erratum/void`。发勘误或作废前由应用按当场版本、说明和剩余时间验证。私有参考解供考后复盘。 |
| 考后讲题 | 读正式答卷、试题版本和勘误时间线，输出 `reply_md, used_refs, followup_practice?, evidence`。补练与答卷分开存，相关证据可关联对应的学习目标。 |
