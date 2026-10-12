# 知序 · RAG 工作台

React + TypeScript + Vite + Ant Design + TanStack Query。所有业务数据来自 FastAPI，未内置模拟业务数据。

## WSL 开发启动

先按照项目 README 启动模型服务、API 和 Worker。前端需要 Node.js >=22.12（建议受支持的 LTS）和 npm，
不使用 Python 虚拟环境安装 JavaScript 依赖。

```bash
cd /home/aq/vscodeproject/enterprise-support-rag/frontend
npm ci
npm run dev
```

浏览器打开 http://localhost:5173。Vite 将 /api 请求代理到 127.0.0.1:8000，浏览器不直接访问模型或数据库。
API 不在本机时可以设置 `API_PROXY_TARGET=http://实际API地址:8000 npm run dev`；不要放入密钥。
不要把开发服务器开放到公网。

同步 Windows 源码到 WSL 时复制 frontend 源码和 package-lock.json，不复制 node_modules/dist。
后端新增 GET /api/v1/documents 分页接口，同时同步 app/api/v1/documents.py，并重建 API 镜像。
本次前端及列表接口没有新增数据库迁移；上传版本功能要求之前的 0002 已完成。

## 页面和行为

- 登录：租户、用户名和演示密码；JWT 仅保存在内存，不写 localStorage/sessionStorage，刷新需重新登录。
- 文档中心：知识库分页列表、单文件上传、业务元数据、更新版本、同名另存选择、任务详情和失败重试。
- 请求幂等：一次表单使用一个键；请求失败后保持表单/文件不变重试沿用原键。修改表单或重新打开会创建新键。
- 文件上限默认 10 MiB，与默认后端配置一致；改变后端限制时同步调整前端。
- 检索实验室：展示精排后候选、RRF/精排分数、片段来源和 trace，不冒充两路原始召回，也不把分数当概率。
- 问答：完整 JSON 响应，无伪流式；Markdown 答案与可展开原文引用。每次独立检索，不传页面历史作为上下文。
- 页面问答记录切换知识库或离开页面后清空；清空不删除服务器消息。暂无历史会话列表和原始文件下载。
- 管理员可上传/更新/重试；成员仅查看与问答，后端仍是最终权限边界。

查询异常显示后端错误码与 request_id。写入请求不自动重试；任务完成/失败后停止轮询。
Markdown 不启用原始 HTML，并屏蔽外部图片，避免跟踪请求；不在浏览器保存模型服务密钥。

## 验证与构建

```bash
npm test
npm run build
```

产物位于 dist。生产部署需通过 Nginx 等服务提供静态文件、为路由配置 index.html 回退，
并将 /api 反代到 FastAPI，启用 HTTPS。vite preview 仅用于构建预览，不是生产服务器。

验收清单：登录失败/过期；切换租户清理缓存；空知识库；重复上传；同名冲突；版本失败旧版可用；
任务重试；跨租户不可访问；检索无结果；问答证据不足/需追问；模型服务不可用。
静态构建和单元测试不等于真实服务端到端验收。
