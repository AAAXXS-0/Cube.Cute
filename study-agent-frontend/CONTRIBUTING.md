# 三人协作指南

建议将项目共用文档和三份任务书作为 GitHub 私有仓库的初始内容，将两位队友加为协作者。之后用 `main` 上的文档和代码作为团队共同版本，进度通过 Issue 和 PR 更新。私有仓库可以先用最简单的分支与 PR 流程。相关操作见 [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow) 与 [邀请个人仓库协作者](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository)。

## 首轮分工

| 主责 | 开发路径 | 可交审的第一件事 |
| --- | --- | --- |
| 前端 | `web/` | F1 样例驱动的工作台。PR 附 A/B/S 的操作步骤和界面截图或短录屏。 |
| 应用后端 | `server/` | B1 焦点与版本 API。PR 附迁移、种子数据、请求及响应示例。 |
| 产品与教学 | `agentarts/` 与教学样例 | T1 两段工作流的最小可调用验证。PR 附输入、输出、部署参数模板和运行结果。 |

应用后端牵头端到端联调。产品与教学负责人维护学习行为及其验收含义。前端负责人维护交互状态和用户动作。共用契约的修改由受影响的负责人一起看，具体文件与决策边界见[共同起步](docs/development/00-start.md)。

## 每个变更怎样交接

1. 建一个短分支。可用 `feat/web-focus-workspace`、`feat/server-focus-history`、`feat/agentarts-return` 等名称。较早打开 Draft PR，写上它对应的任务编号和示例。
2. 每个 PR 尽量包含一个可验证结果。实现附实际运行方法或请求样例，界面附可点击路径，工作流附同输入可复跑的输出与失败示例。
3. 改共用数据或行为时，把[共用开发契约](docs/development/01-contract.md)、[联调数据](docs/development/examples.json)和受影响的[验收步骤](docs/development/05-acceptance.md)放进同一变更。接口变动可先发契约 PR，让两边并行跟进。
4. 涉及网页与 API 时由另一侧成员确认一次。两段比赛工作流的 PR 需走一遍真实调用。以当前已接通的范围合入 `main` 并更新对应任务，标出仍使用 mock 的场景。

PR 内容可直接按下面的顺序写。

```markdown
## 做了什么

## 按什么步骤、用哪份数据复现

## 实际观察到的结果

## 接口、数据版本或部署变化
```

## 可克隆、可联调

- 首个工程 PR 记录应用启动、数据库初始化、样例装载和两种工作流模式的实际命令。另一人从干净目录复现后把命令写回 README。
- 仓库用合成教材、合成学习记录和脱敏的工作流回执。AgentArts 部署凭据与模型密钥通过约定的环境变量或团队密钥渠道交接。环境变量模板可以入库，真实值、个人学习记录、内部原始文档和交接 ZIP 放在仓库外。
- UI、应用与工作流各自有联调样例。遇到接口不符时，先把实际请求、出错字段和预期结果贴在相应 PR，再决定修正哪一侧。
- 验收按[首版验收表](docs/development/05-acceptance.md)核对。赛前建立可复现的演示版本，并记录所用工作流部署、应用提交和样例版本。
