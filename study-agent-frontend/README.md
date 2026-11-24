# 学习辅助 Harness · 前端开发交接

这是电脑网页首版的一份角色交接包。两种学习入口及共同验收按同一套产品设计执行。

第一份可交付结果是用联调样例完成学习工作台，演示在 A 学习时浏览 B、从 A 开支线 S、再返回 A 并回查原文。

## 从这里开工

1. 读 [AGENTS](AGENTS.md) 和[共同起步](docs/development/00-start.md)。
2. 打开 [前端开发任务书](docs/development/02-frontend.md)，从第一项任务开始。
3. 对照[共用开发契约](docs/development/01-contract.md)和[联调数据](docs/development/examples.json)实现。
4. 按[联调与验收](docs/development/05-acceptance.md)记录结果。使用[协作指南](CONTRIBUTING.md)与队友交接。

## 直接交给开发 Agent

> 读 AGENTS.md、共同起步、共用开发契约、前端任务书及 examples.json。按前端任务书从 F1 开始实际开发，先用样例完成可点击的 A → S → A 和浏览 B 的场景，覆盖任务书的接口状态及验收步骤。按现有项目结构提交工作，并说明 mock 与真实 API 的切换方法。

## 当前可运行版本

`web/` 包含前端 v0.1.0 的 A/B/S 学习工作台。Node.js 24 下运行：

```bash
cd web
npm install
npm run dev
```

打开 `http://localhost:5173/workspace/g_network`。默认使用 localStorage mock，HTTP 切换方式、演示步骤和测试命令见 [web/README](web/README.md)；本次实测记录见 [验收记录](web/ACCEPTANCE.md)。

## 设计和样例

[产品功能大纲](docs/product-outline.md) · [设计稿索引](docs/design-index.md) · [自编短教材](docs/development/fixtures/network-mini-textbook.md)
