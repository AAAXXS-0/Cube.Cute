# 续学 · 前端 v0.1.0

桌面优先的 React 学习工作台。当前版本使用团队 `examples.json` 提供可操作的 A/B/S 本地样例，并实现同形 HTTP API 客户端。

## 启动

要求 Node.js 24。

```bash
npm install
npm run dev
```

打开 `http://localhost:5173/workspace/g_network`。

```bash
npm run typecheck
npm run test
npm run test:e2e
npm run build
```

浏览器测试默认使用本机 Microsoft Edge，无需下载额外浏览器。

## 核心演示

1. 初始焦点为 A「DNS 查询」。点击 B「缓存与 TTL」只浏览，不切焦。
2. 向 Teacher 提问。问题与回复归 A，引用指向 B。
3. 点击「由此开支线」，进入 S 并保存一段支线成果。
4. 返回 A，页面先恢复原断点，再轮询续学任务。
5. 在续学答复下打开实际采用的 S 原记录。

顶部 Mock 菜单可模拟下一次续学失败或重置样例。焦点、断点、记录和任务保存在 localStorage；编辑器草稿按节点分别保存。

## Mock / HTTP

复制 `.env.example` 为 `.env.local`：

```text
VITE_API_MODE=mock
VITE_API_BASE_URL=http://localhost:3000/api/v1
```

- `mock`：默认模式，无需后端，使用 `../docs/development/examples.json`。
- `http`：使用团队 `/api/v1` 契约，写入请求自动带 `Idempotency-Key`。

页面只依赖 `StudyApi`，不直接读取样例 JSON。AgentArts 由应用后端接入，浏览器不保存任何平台密钥。

## 当前边界

- v0.1.0 完成 F1 核心工作台；教材与目标准备路由明确标记为 v0.2.0。
- 计时自测、完整反馈、掌握证据和 Markdown 导出不在本版本。
- HTTP 客户端已实现，但真实后端尚未联调；当前验收结果仅针对 mock。
- 节点完成与掌握证据保持分离，本版本的路线计数仅展示样例进度。

## Git

前端集成分支：`frontend`。当前功能分支：`frontend-v0.1.0-focus-workspace`。版本标签：`frontend-v0.1.0`。功能分支通过 PR 合入 `frontend`，未经明确要求不推送远程，不推送 `main`。
