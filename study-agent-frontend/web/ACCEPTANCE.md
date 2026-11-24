# v0.1.0 本地验收记录

日期：2026-11-24。范围：F1 A/B/S 学习工作台。数据与回复均为团队合成样例，不代表真实 AgentArts 调用结果。

## 实际执行

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| TypeScript 与生产构建 | `npm run build` | 通过，无体积警告 |
| API 状态测试 | `npm run test` | 7 项通过 |
| Edge 浏览器验收 | `npm run test:e2e` | 5 项通过 |
| 依赖安全审计 | `npm audit --audit-level=moderate` | 0 个已知漏洞 |

## 已观察到的核心结果

- A 学习时浏览 B，焦点保持 A；提问和迟到回复归 A，B 作为引用。
- 从 A 创建 S 后焦点切换到 S；保存成果、返回 A 后恢复原断点并显示续学任务。
- 续学答复使用实际 S 记录，能够打开该记录的冻结版本。
- 刷新后恢复焦点与各节点本地草稿。
- 续学失败可在原焦点重试，原支线成果不丢失。
- 另一标签页切焦后，旧页面提交返回 `FOCUS_CHANGED`，未提交文字仍保留。
- 出处面板可打开和关闭，版本缺失返回 `REF_UNAVAILABLE`，打开出处不改变焦点。

## 尚未联调

- 真实 Fastify / `/api/v1` 后端。
- AgentArts `resume_branch` 与 `textbook_plan` 部署。
- 教材与目标准备、理解反馈、掌握证据、Markdown 导出和计时自测。
