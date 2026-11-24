# AgentArts 控制台接线与部署

## 两个流程的共用配置

1. 创建任务型工作流 `textbook_plan` 和 `resume_branch`。开始节点设置 `payload_json` 为业务必填 `String`。试运行输入使用 `python -B -m agentarts.run fixture <样例>` 的整行输出。
2. 代码节点粘贴 [workflow.py](workflow.py) 全文。每个节点配置下表列出的输入参数，`step` 是固定的 `String`。除 `append_analysis` 外，每个代码节点都引用开始节点的 `payload_json`。`allow_repair` 用固定的 `Boolean`。常用输出声明为 `action`, `result_json`, `context_json`, `repair_json`（均为 `String`）和 `section_inputs`（`Array<String>`）。`append_analysis` 只输出 `analysis_json`（`String`）。
3. 大模型节点的系统提示词使用 `prompts/` 中指定文件，用户提示词填 `{{context_json}}` 并绑定实际输入。输出格式选文本并关闭输出流，保留 `raw_output` 为 `String`。关闭会话记忆，每次只看所绑定的工作快照。模型节点之间的 JSON 交给代码节点解析。
4. 每当某代码节点返回 `action=done`，沿终态分支接到同一个变量聚合节点。将这些终态节点的 `result_json` 加入一组 String 聚合变量。只有终态返回非空 `result_json`。结束节点只声明一个结构化输出 `result_json`，引用该聚合变量。如果当前工作空间要求填写「指定回复」，输入参数也引用同一变量，指定回复只填 `{{result_json}}`。

[代码节点](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0067.html) · [大模型节点](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0062.html) · [变量聚合](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0085.html) · [结束节点](https://support.huaweicloud.com/lowcode-agentarts/end_node.html)

两段比赛流程直接用应用冻结的原文与来源运行。按 T4 工具契约核对的公开资料可由应用在调用前登记进 `textbook_plan` 的 `source_catalog`，支线续学继续用本次提供的支线正文和 `allowed_refs`。[T4 工具联调](README.md#t4-教学工具)

## `resume_branch`

| 节点 | 参数与去向 |
| --- | --- |
| 续学输入校验 | `step=prepare_resume`。`action=run` 转大模型，否则走终态。 |
| 续学大模型 | [resume-branch.md](prompts/resume-branch.md)。`context_json` 引用续学输入校验的同名输出。 |
| 续学结果校验 | `step=finish_resume`，`draft_json` 引用大模型的 `raw_output`。结果进入终态。 |

先试 `resume`、`resume-alt`。原问题和 A 的断点相同，核对返回的解释、下一步和 `used_refs`。再试空支线、无关内容及失效版本。选用的支线记录须能从应用打开当时的正文。

## `textbook_plan`

| 节点 | 参数与去向 |
| --- | --- |
| 编排输入校验 | `step=prepare_textbook`。`action=run` 转分节循环，`done` 转终态。 |
| 分节循环 | 用 `section_inputs` 做数组循环，中间变量 `analysis_json` 初始为字符串 `[]`。循环体按下文配置。 |
| 章节收齐 | `step=collect_sections`，`analysis_json` 引用分节循环输出。`action=run` 转全局编排，`done` 转终态。 |
| 全局编排 | [textbook-draft.md](prompts/textbook-draft.md)，`context_json` 引用章节收齐的输出。当前草案为本节点的 `raw_output`。 |
| 复核准备 | `step=prepare_review`，`draft_json` 引用当前草案。`run` 转独立验题，`repair` 转修补，`done` 转终态。 |
| 独立验题 | [textbook-independent.md](prompts/textbook-independent.md)，`context_json` 引用复核准备输出。 |
| 对照准备 | `step=compare_review`，输入 `draft_json` 和 `independent_json`，分别引用当前草案、独立验题 `raw_output`。`run` 转对照验收，`repair` 转修补，`done` 转终态。 |
| 对照验收 | [textbook-review.md](prompts/textbook-review.md)，`context_json` 引用对照准备输出。 |
| 发布前校验 | `step=finish_textbook`，输入 `draft_json`、`independent_json` 和 `review_json`，最后一项引用对照验收的 `raw_output`。`repair` 转修补，`done` 转终态。 |

分节循环体从「循环输入」进入分节大模型。用 [section-analysis.md](prompts/section-analysis.md)，将循环 `item` 绑定为 `context_json`。下一代码节点设 `step=append_analysis`，`section_json` 引用当前 `item`，`analysis_output` 引用分节大模型的 `raw_output`，`analysis_json` 引用循环同名中间变量。用变量赋值把代码输出的 `analysis_json` 保存回循环中间变量，再连至「循环输出」。循环的对外 `analysis_json` 输出引用该中间变量。汇编按 `section_id` 核对齐套、教材原节的版本与位置以及编排目标。问题节可重新分析并覆盖对应条目。[数组循环配置](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0329.html)

修补分支的三个来源是复核准备、对照准备和发布前校验。第一遍三个节点的 `allow_repair` 均设为 `true`。在修补路径使用一个 String 变量聚合组，接收实际触发修补的节点输出 `repair_json`，将其绑定给修补大模型的 `context_json`。提示词用 [textbook-draft.md](prompts/textbook-draft.md)，修补结果成为新的草案。复制复核准备至发布前校验这段，让第二遍节点引用新草案，`allow_repair` 均设为 `false`。第二遍继续工作或进入终态。缺关键材料时可直接返回 `needs_source`。

先试用三节网络短教材，再跑缺节、7 天和 3 天、跨节 `textbook-rate` 与等价节点复用。汇编使用原节定位、按节分析和摘录，独立验题再回读本次原节。长教材要实测输入、每节分析、验题的窗口和时限。平台预算不足时，后续可以把分组分析拆成子工作流，用同版本产物按 `section_id` 收齐后再汇编。[工作流限制](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0043.html) · [嵌套编排](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0330.html)

## 发布调用与回执

1. 调试通过后提交版本并部署到实例，拷贝控制台为该部署生成的 API 调用信息。配置可供 API 调用的模型。凭据通过团队密钥渠道配置到环境，变量名见 [deployment.env.example](deployment.env.example)。使用 API Key 的部署用 `*_API_KEY`。其他部署可用 `*_HEADERS_JSON` 提供控制台要求的认证请求头。
2. 从 `Cube.Cute` 根目录执行下方调用。`*_RESULT_PATH` 或 `--result-path` 可以覆盖脚本的响应提取路径。文档示例的流式响应取 `workflow_finished` 终态的 `data.outputs.user_fields.result_json`。保留 JSON 字符串，解析并核对原 `request_id` 后再验收。

```powershell
python -B -m agentarts.run invoke resume --receipt agentarts/resume.receipt.json
python -B -m agentarts.run invoke resume-alt --receipt agentarts/resume-alt.receipt.json
python -B -m agentarts.run invoke textbook --receipt agentarts/textbook.receipt.json
python -B -m agentarts.run invoke textbook-missing
```

带 `--receipt` 的调用需要配置对应部署版本，生成的回执含输入、输出、应用外调用耗时与可用的执行 ID。仅用合成测试资料生成可交付回执。App 端另记 `job_id`、应用提交、输入或发布版本、源码回查结果与用户侧耗时。至少用一次模型超时、输出校验失败或缺材料确认应用提示及重试行为。验收后从控制台导出两段实际部署用的 JSONL，保存对应模型配置、版本和复跑方法。[部署](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0053.html) · [API 调用](https://support.huaweicloud.com/bestpractice-agentarts/agentarts_06_0022.html) · [响应事件](https://support.huaweicloud.com/api-agentarts/agentarts_07_0056.html) · [导入导出](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0058.html)
