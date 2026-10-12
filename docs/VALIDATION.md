# 第一阶段验证记录

日期：2026-10-11。

## 已执行

| 检查 | 环境 | 结果 | 证明范围 |
|---|---|---|---|
| Python pytest | Windows 已有 Python 3.12.4 | 28 项通过 | API、业务逻辑、临时 SQLite 和外部服务替身 |
| 解析器独立验证 | /home/aq/vscodeproject/.venv，Python 3.12.14 | 4 项通过 | 真实 pypdf/python-docx 解析、页码/块定位和 OCR 提示 |
| Python compileall | Windows 已有 Python | 通过 | app、model_services、scripts、migrations 语法 |
| docker compose config --quiet | WSL 已有 Docker Compose | 通过 | 应用 Compose 配置可解析；未构建或启动 |
| 冻结迁移定义比对 | 单元测试 | 通过 | 初始表字段、索引与 ORM 一致，DDL 可编译为 MySQL |
| 模型封装参数检查 | WSL 已安装 FlagEmbedding 源码只读检查 | 构造参数对应 | 未加载权重、未运行模型推理 |

测试替身只存在于 tests/，生产路径不生成假向量，也不回退为固定答案。
解析验证只创建内存中的样例，不读取用户私有文档。

## 测试覆盖

- 登录、未认证拒绝、禁止客户端注入租户。
- 上传、任务 READY、搜索与服务端引用。
- 向量写失败后重试、同一任务重复投递。
- 非法上传、格式不匹配、错误编码与代码标点保留。
- Token 长度兜底与原文覆盖。
- RRF 排名参考计算与重复候选保护。
- 向量返回错误租户候选时，在精排和生成前拦截。
- 成员不能上传、其他租户不能查看文档/任务/知识库。
- 版本条件在权威数据库中复核。
- 生成期间撤销知识库成员权限，返回 EVIDENCE_CHANGED。
- 模型引用不存在的证据 ID 时拒绝返回。
- 无候选不调用 LLM；缺少升级版本时追问。
- Embedding 版本、维度和 Reranker 返回数量校验。
- PDF 文本提取与扫描/空白页 OCR_REQUIRED。
- DOCX 表格与段落次序、无虚构页码。
- API OpenAPI 路由存在性。

## 没有执行、不得据此宣称通过

- 在真实 MySQL 上运行 Alembic 迁移。
- 真实 Celery/Redis 投递和 Worker 崩溃恢复。
- 项目 Bucket 创建、上传和真实 MinIO 读取。
- 项目 Milvus Collection 创建及 Dense/Sparse Hybrid Search 联调。
- BGE-M3/Reranker 权重加载、推理性能和真实检索质量。
- 外部 LLM 请求、引用语义正确率和端到端实测延迟。
- Docker 镜像构建、容器运行、GPU 配置。
- 高并发、长时间稳定性、生产安全验收。

## 已有环境与限制

用户指定 WSL 环境已有 SQLAlchemy、pypdf、python-docx、transformers、FlagEmbedding、torch 等。
缺少 FastAPI、Celery、MinIO SDK、PyJWT、python-multipart、Alembic、pytest 等依赖。
PyMilvus 当前为 3.0.2，服务端 Milvus 为 2.4.4；项目约束 2.4.x，需在目标环境确认并处理兼容性。

先前在 Windows 项目目录创建了未投入使用的 .venv；依赖下载未获许可，没有完成安装。
未修改用户指定的 WSL 虚拟环境，未修改已有 Compose、网络、端口或容器。
未读取既有数据库密码或客户数据，未发送外部 LLM 请求。

本地测试出现一条已安装 FastAPI/Starlette 针对 httpx TestClient 的弃用提示。
它不影响本次结果；目标环境完成依赖解析与锁定后应再次运行测试。

## 完整验收前置条件

1. 确认共享 WSL 环境的依赖变更方案，尤其 PyMilvus 版本。
2. 配置独立项目数据库账号、MinIO 凭据、JWT 与内部模型密钥。
3. 明确 WSL 进程连接 MinIO 的地址，或使用应用 Compose 连接现有网络。
4. 固定 Embedding/Reranker revision，确认 CPU/GPU 与缓存路径。
5. 配置可用 LLM 服务的基础地址、模型及密钥。
6. 按 README 初始化，再上传模拟资料执行真实端到端验收。

本记录描述已观察到的结果，不包含虚构的 Recall、吞吐、延迟或生产用户量。

