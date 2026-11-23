# Teacher 与 Keeper 的工具契约

这是首版应用侧工具约定。两位 agent 共享个人学习资料的检索和原文读取。Teacher 还负责查找、核对公开资料。工具读取资料并返回依据。反馈、推荐、关联及撤回走已有结构化教学输出，由应用校验、保存和发布。

## 四个工具

| 工具 | 谁在何时用 | 参数 | 成功返回的 `data` |
| --- | --- | --- | --- |
| `search_study_records` | Teacher 查当前问题需要的内容，keeper 查能解释的旧联系。 | `query` 查询文本，`scope?` 为 `focus_node/focus_graph/learner_history`，`limit?` 最多返回几条。 | `matches`。每条含 `ref, title, excerpt_md`，可附 `corrected_by_ref` 指向后续纠正。按相关性返回资料、笔记或已保存学习记录的具体版本。 |
| `read_reference` | 两者拿到引用后，读该版原文和所在位置。用户点名引用、应用已知来路或搜索命中均可提供引用。 | `ref`。沿用应用的 `{kind,id,revision,locator?}`。 | `ref, title, body_md`，可附 `corrected_by_ref`。与应用的版本查询复用同一原文读取逻辑。 |
| `search_public_sources` | Teacher 在从目标开局、核对教材疑点或补查备考资料时找公开来源。 | `query` 查询文本，`limit?` 最多返回几条。 | `matches`。每条含 `candidate_id,title,url,excerpt_md`。作为待核对来源。 |
| `read_public_source` | Teacher 核对从网上找到的来源，或应用已登记的用户提供的公开链接。 | `candidate_id`，可选 `section` 小节名称。 | `ref,title,url,accessed_at,body_md`。应用留存这次用到的小节和定位，生成来源版本，供候选、补充材料或勘误引用。 |

## 怎么接

- 工具参数由模型提供。应用从原教学任务带入学习者、触发时的焦点、操作类型和当时可用的资料范围。同一工具供两个模型或工作流复用。工具调用复用已有的 `{data}`、`{error:{code,message,details}}` 响应约定。
- `search_study_records` 默认从当前图查。已知引用先直接读取。确有必要才扩大到该学习者的历史，其他图仍须对该学习者可见。首版用结构化范围、关键词和已有关联即可开始，语义检索可按实测增补。两类搜索联调默认返回 5 条，可请求 1 到 10 条。
- 用到某段资料时，工作输入已经有原文就直接用。否则读取搜索命中的原文，确认实际内容、当时版本和是否已有纠正。成功读取的 `ref` 由应用登记到本任务的可引用范围。精确版本不存在时返回 `REF_UNAVAILABLE`。搜索无结果返回 `matches: []`，服务失败用 `TOOL_UNAVAILABLE`，由 teacher 告知依据是否充足。
- 公开检索的摘要是找资料的线索。候选 ID 取自本任务搜索结果或应用已登记的用户链接。能读到实际内容才作为教学出处。打不开来源时，可换来源或请用户补材料。正文和外部网页用于取证，教学操作仍由当前任务决定。用到的公开原文片段、地址和查阅时间随结果保存。
- 应用侧仍持有正式状态。Teacher 可以输出核查结果、复习建议，或用提示 ID 提议撤回。Keeper 输出关联类型、理由和出处。焦点切换、完成标记、发布路线、采纳候选、改动考试及撤回提示由应用执行。

## 按场景开放

| 场景 | 首版接法 |
| --- | --- |
| 普通问答和检查 | 应用先传当前问题、课内目标和用户点名材料。Teacher 按需用前两个工具。保留被纠正原稿及对应反馈的版本。 |
| Keeper 提示与事后复核 | Keeper 用前两个工具独立查找并给出处。若 teacher 已引用同一资料，将关联去重。需要撤回时 teacher 用原任务快照复核并给理由。正文答复可先返回。 |
| 从目标开局、备考与教材补充 | Teacher 用后两个工具查找并核对来源。应用将采用的来源登记进 `source_catalog`，候选和限时清单用这些来源。教材规划需要补充依据时，可以在调用前准备进输入快照。 |
| 两段 AgentArts 工作流 | `resume_branch` 直接消费原问题、支线原文和允许引用列表。`textbook_plan` 直接消费章节正文、资料目录与范围。两段都能用现有 [T1 样例](examples.json) 接通。确有运行时查找需求时，可将应用接口接成平台节点，保留同一份工具约定。[AgentArts HTTP 请求节点](https://support.huaweicloud.com/lowcode-agentarts/http_node.html) · [基于 API 创建插件](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0126.html) |
| 计时自测 | 作答中的用户对话只走规则问答，应用对该任务禁用教学检索。需要时返回 `EXAM_LOCKED`。后台验题另取该场题面和用户报告，交卷后的复盘恢复按需读取。 |

## 谁交付

- **应用后端**实现工具处理器，复用学习记录、版本读取及来源存储。接入可替换的公开搜索和正文读取，提供与 [`tool_cases`](examples.json) 同形的联调样例。两段比赛工作流先用冻结快照跑，工具接入可并行。
- **产品与教学**把工具用法写进对应提示词和任务编排，规定何时主动查、何时继续解释、何时返回缺资料。用查到有用旧笔记、无关结果、版本缺失和公开来源打不开的例子验收。按实际需要决定是否在 AgentArts 接应用接口。
- **前端**按现有引用、候选和关联接口显示结果。查找和读原文由应用与教学服务交互，用户从条目点回来源。

[共用开发契约](01-contract.md) · [联调与验收](05-acceptance.md) · [Teacher、Keeper 与检索](../teacher-keeper-retrieval-draft.md)
