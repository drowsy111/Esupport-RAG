# 项目目录结构

本文按仓库当前代码整理。项目根目录为仓库根目录，不包含其父目录中的个人文档或其他项目。

```text
enterprise-support-rag/
├── app/
│   ├── api/                   # FastAPI 依赖、路由与 v1 接口
│   ├── core/                  # 配置、异常、日志
│   ├── db/
│   │   └── models/            # SQLAlchemy 数据模型
│   ├── generation/
│   │   └── prompts/           # 回答和 Query Planner 提示词
│   ├── indexing/              # Milvus Collection schema
│   ├── ingestion/
│   │   └── parsers/           # Markdown、DOCX、PDF 解析器
│   ├── integrations/          # Embedding、Reranker、LLM、Milvus、对象存储客户端
│   ├── repositories/          # 数据访问与授权候选查询
│   ├── retrieval/             # 过滤、融合、去重、邻文窗口、精排与上下文
│   ├── schemas/               # API、文档块、检索、Query Plan 和问答数据模型
│   ├── security/              # 身份、租户、知识库权限与上传校验
│   ├── services/              # 文档、入库、检索和聊天业务编排
│   ├── workers/               # Celery 应用及异步任务
│   ├── lifespan.py            # API 生命周期和共享资源管理
│   └── main.py                # FastAPI 应用入口
├── data/
│   ├── synthetic/             # 合成演示知识资料
│   └── sources_manifest.jsonl # 数据源清单
├── deploy/                    # API/Worker Dockerfile 和部署配置
├── docs/                      # 范围、运行、迁移、评估和项目结构文档
├── evaluation/
│   ├── configs/               # 评估配置
│   ├── datasets/              # 开发评估数据集
│   └── reports/               # 评估结果
├── frontend/                  # React + TypeScript + Vite 前端
│   └── src/
├── migrations/
│   └── versions/              # Alembic 数据库迁移
├── model_services/
│   ├── embedding/             # BGE-M3 Embedding HTTP 服务
│   └── reranker/              # Reranker HTTP 服务
├── scripts/                   # 初始化、环境检查、导入和解析验证脚本
├── tests/
│   ├── fixtures/
│   ├── integration/
│   ├── regression/
│   ├── security/
│   └── unit/
├── .env.example               # 环境变量模板
├── compose.yaml               # API、Worker 及可选模型服务
├── pyproject.toml             # Python 依赖、包和工具配置
├── alembic.ini                # Alembic 配置
└── README.md                  # 安装、配置、运行和验证说明
```

本地 `.env`、`.venv/`、`models/`、`frontend/node_modules/`、构建产物、缓存和运行时文件不属于源代码结构，均不应提交到 Git。`runtime/` 用于本地运行时数据；具体内容由 `.gitignore` 管理。

## 关键模块职责

### API 与业务编排

| 路径 | 职责 |
|---|---|
| `app/main.py` | 创建 FastAPI 应用，注册请求上下文、中间件和异常处理。 |
| `app/api/router.py` | 汇总并挂载 API 路由。 |
| `app/api/v1/` | 登录、文档上传/查询、任务、知识库、检索和聊天接口。 |
| `app/services/document_service.py` | 文档上传、版本和任务相关业务流程。 |
| `app/services/ingestion_service.py` | Worker 中执行解析、切块、向量化、索引和发布流程。 |
| `app/services/retrieval_service.py` | 编排召回、权限复核、邻文扩窗和重排。 |
| `app/services/chat_service.py` | 编排检索、证据构造、LLM 调用、引用复核和消息保存。 |

### 文档解析、清理与切块

| 路径 | 职责 |
|---|---|
| `app/ingestion/parsers/registry.py` | 根据文件类型选择解析器。 |
| `app/ingestion/parsers/markdown.py` | 解析 Markdown 标题、段落和代码围栏，生成带标题路径的结构块。 |
| `app/ingestion/parsers/docx.py` | 解析 Word 段落、标题样式和表格。 |
| `app/ingestion/parsers/pdf.py` | 按页提取 PDF 文本和页码；不推断 OCR 或可靠标题结构。 |
| `app/ingestion/cleaning.py` | 统一换行并移除 BOM、空字符；保留结构性文本。 |
| `app/ingestion/sentence_chunking.py` | 按句末标点及代码/列表/表格等结构边界切分；同一块内的短正文句按 BGE Token 数累积，长单元按上限切分，并保存块内字符位置。 |
| `app/ingestion/chunking.py` | 旧版滑动窗口切块函数及 tokenizer 加载器；新入库主流程使用 `sentence_chunking.py`。 |
| `app/ingestion/pipeline.py` | 连接文件解析与当前句子切块逻辑。 |
| `app/schemas/parsed_document.py` | 定义解析器输出的文档块及元数据结构。 |
| `app/schemas/chunk.py` | 定义待持久化的文本块结构。 |

### 检索与问答

| 路径 | 职责 |
|---|---|
| `app/integrations/milvus_client.py` | Dense + Sparse 混合检索及 RRF 融合。 |
| `app/repositories/chunk_repository.py` | 从 SQL 读取并复核租户、知识库、版本、正文哈希和授权范围。 |
| `app/retrieval/deduplication.py` | 去除重复候选。 |
| `app/retrieval/sentence_window.py` | 仅在兼容的文档版本/章节范围内扩展并合并邻文窗口，受窗口 Token 预算限制。 |
| `app/integrations/reranker_client.py` | 调用重排模型服务。 |
| `app/retrieval/reranking.py` | 按重排分数排序并截取 Top-K。 |
| `app/retrieval/context_builder.py` | 为候选分配引用 ID，按字符预算构造 LLM evidence。 |
| `app/integrations/llm_gateway.py` | 调用 Chat Completions JSON 模式，检查上游状态、响应结构、结束原因和生成结果 schema，并映射为可诊断错误。 |
| `app/generation/prompts/answer.md` | 限制模型仅依证据回答、规定 JSON 结构及标题类歧义问题的澄清行为。 |
| `app/generation/prompts/query_plan.md` | 指导模型选择直接检索、子问题拆解或澄清，不生成答案。 |
| `app/generation/citations.py` | 校验模型引用 ID，并由服务端生成引用内容。 |
| `app/schemas/chat.py` | 定义聊天输入、最终回答状态、声明和引用的校验结构。 |
| `app/schemas/query_plan.py` | 独立校验 Planner 的 direct/decompose/clarify 路由及对应字段。 |

### 数据、模型服务与后台任务

| 路径 | 职责 |
|---|---|
| `app/db/models/` | ORM 数据模型，包括租户/身份、知识库、文档/版本、Chunk、任务和对话。 |
| `app/repositories/` | 数据库查询封装。 |
| `migrations/versions/` | 数据库 schema 变更历史；部署前按需执行 Alembic 迁移。 |
| `app/workers/celery_app.py` | 配置 Celery Worker 和任务队列。 |
| `app/workers/tasks.py` | 定义异步摄取任务。 |
| `model_services/embedding/` | 加载 BGE-M3 并提供向量编码 HTTP 接口。 |
| `model_services/reranker/` | 加载重排模型并提供重排 HTTP 接口。 |
| `app/integrations/object_storage.py` | 封装原始文件对象存储读写。 |
| `app/integrations/embedding_client.py` | 调用 Embedding HTTP 服务并校验返回向量。 |
| `app/indexing/collection_schema.py` | 定义 Milvus 集合字段与索引。 |

### 前端、脚本、评估与测试

| 路径 | 职责 |
|---|---|
| `frontend/src/` | React 页面、API 封装、业务类型和样式。 |
| `frontend/package.json` / `package-lock.json` | 前端依赖与锁定版本。 |
| `scripts/bootstrap.py` | 初始化项目所需基础资源。 |
| `scripts/check_environment.py` | 检查运行环境和依赖配置。 |
| `scripts/import_documents.py` | 批量导入文档。 |
| `scripts/seed_demo.py` | 初始化演示租户和知识库数据。 |
| `scripts/verify_parsers.py` | 验证文档解析行为。 |
| `evaluation/datasets/` | RAG 开发评估问题与标注数据。 |
| `evaluation/configs/`、`evaluation/reports/` | 评估运行配置和结果输出位置。 |
| `tests/unit/` | 切块、模型契约、迁移定义等单元测试。 |
| `tests/integration/` | 上传、任务、检索窗口和工作流测试。 |
| `tests/security/` | 租户隔离等安全测试。 |
| `tests/fakes.py` | 提供测试用 tokenizer、向量库和模型替身。 |

## 主流程入口速查

- **文档入库**：`app/workers/tasks.py` → `app/services/ingestion_service.py` → `app/ingestion/pipeline.py` → parser → `sentence_chunking.py` → embedding → Milvus。
- **聊天问答**：`app/api/v1/chat.py` → `app/services/chat_service.py` → `app/services/retrieval_service.py` → Milvus 混合检索 / SQL 授权复核 / 窗口扩展 / Reranker → `context_builder.py` → `llm_gateway.py` → 引用校验。
- **数据库升级**：`migrations/versions/`；只有 schema 变更需要执行 Alembic，不是每次代码发布都要迁移。
