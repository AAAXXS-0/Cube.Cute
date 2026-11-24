# 教学与 AgentArts

本目录按 [Teaching 与 AgentArts 任务书](../study-agent-teaching-agentarts/docs/development/04-teaching-agentarts.md) 实现 `textbook_plan` 和 `resume_branch` 的代码节点、提示词与调用验证。对外使用 [共用契约 1.0](../study-agent-teaching-agentarts/docs/development/01-contract.md#应用与-agentarts-的调用)。学习图的发布、焦点切换、重试幂等和记录写入由应用负责。

当前可从本地复跑代码节点和模拟模型输出。AgentArts 的平台部署、模型教学质量和应用 job 真实调用等平台配置就绪后验收。

## 本地复跑

在 `Cube.Cute` 根目录用 Python 3.9 或以上版本执行。依赖均为标准库。

```powershell
python -B -m unittest discover -s agentarts/tests -v
python -B -m agentarts.run cases
python -B -m agentarts.run fixture textbook
python -B -m agentarts.run fixture resume-alt --format api
```

如果当前桌面环境的 Python 在 Codex bundled runtime 里，可用该解释器执行。

```powershell
$teachingPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $teachingPython -B -m unittest discover -s agentarts/tests -v
& $teachingPython -B -m agentarts.run fixture resume
```

`fixture` 默认打印贴进开始节点 `payload_json` 的字符串内容。`--format api` 打印 API 请求体。`--format expected` 打印合成预期，用于 mock。用 `verify <样例> <响应文件>` 校验保存的 JSON 或 SSE 回执。

| 样例 | 验收项 |
| --- | --- |
| `textbook`, `textbook-missing` | 覆盖三节、全书／核心路线、A 到 B 的必要前置及 C 的独立起步。剔除 `sec_2` 后指出待补节。 |
| `textbook-add` | 旧 DNS 节点可复用，旧 TTL 节点的学习目标不足以覆盖新增要求。 |
| `textbook-7`, `textbook-3` 及各自 `-assessment` | 至少七天可生成限时路线。三天返回带出处的优先清单。对照实际考核范围与采用教材基础时的理由。 |
| `resume`, `resume-alt` | 同一原问题用两篇支线成果。检查解释和下一步随条件改变，引用 `rec_s_note` 和 `rec_s_alt` 各自的第 1 版。 |
| `resume-empty`, `resume-unrelated`, `resume-stale` | 继续处理原问题并给一步具体动作。空支线、无关正文和失效版本均不作为续学成果引用。 |
| `textbook-rate` | 两章四节的变化率教材跨节编排。预期草案将第一章平均速度用于第二章差商，在不同题中验算并保留原节出处。 |

7 天路线和 3 天清单用例沿用任务书规则。清单的工作流 `result` 以 `{kind, items, note_md}` 交付，应用补自己的 `graph_id`。接入时由后端按共用契约核对这一映射。短教材样例直接读取交接目录的 `examples.json`。

本地测试覆盖独立验题、修补后再验收、来源和版本、路线与活动结构，以及合成的 HTTP 和 SSE 响应。T4 的教学提示词在 [teacher-keeper.md](prompts/teacher-keeper.md)。[补充用例](fixtures/teaching-cases.json) 包含 merge、Keeper 复核、考中规则回应、勘误、作废和考后复盘，配合 `examples.json` 里的 `goal_flow`、`feedback_case`、`keeper_case` 联调。

## T4 教学工具

按 [工具契约](../study-agent-teaching-agentarts/docs/development/06-agent-tools.md) 启用对应工具。`teaching_config(role, operation)` 生成系统提示词与四个工具中本任务可用的函数声明，声明含 `name, description, parameters`。后端将声明交给模型 provider，并用本次教学任务的学习者、焦点和资料范围执行真实工具处理器。工具调用成功后，应用按契约登记本次可引用的版本和位置。

为教材编排准备公开资料时，从成功的 `read_public_source.data` 取 `ref.id`、`ref.revision`、`ref.locator`、`title`、`url` 和 `accessed_at`，把 `body_md` 存为 `source_catalog` 条目里的 `excerpt_md`。教材工作流据此校验来源的精确版本和位置。

| 场景 | 开放工具 |
| --- | --- |
| Teacher 问答、核查、练习、下一步建议、复核关联、考后复盘 | `search_study_records`、`read_reference` |
| Keeper 找关联 | `search_study_records`、`read_reference` |
| Teacher 目标开局、备考、教材补充 | `search_public_sources`、`read_public_source` |
| 考中规则问答和后台验题 | 使用各自的任务快照 |

以下命令输出模型配置和 A10 的本地复跑记录。

```powershell
python -B -m agentarts.run teaching-config teacher ask
python -B -m agentarts.run tool-replay
python -B -m agentarts.run tool-replay keeper_cross_graph
python -B -m agentarts.run tool-replay teacher_public_source --alternate
python -B -m agentarts.run tool-replay teacher_during_exam
```

`tool-replay` 读取 `examples.json` 的 `tool_cases` 与补充的无关关联样例，输出标为 `mock`。本地校验检查工具场景、版本及定位、候选归属和读取后可引用的范围。实际联调中还要根据原文检查推荐和关联是否有教学用途，并在应用中核对跨图权限、真实搜索与考中限制。

## 发布与验收

按 [控制台接线与部署](DEPLOYMENT.md) 创建两段工作流。先在平台试跑，再用 `agentarts.run invoke` 从应用外调用。记录两份续学对照、短教材正常结果和待补件结果。最后从应用真实 job 执行两条最短链路，按 [首版验收](../study-agent-teaching-agentarts/docs/development/05-acceptance.md) 对照页面、应用任务和平台回执。
