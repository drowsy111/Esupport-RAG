# 企业软件交付与技术支持 RAG 知识库平台

第一阶段后端：上传 -> 异步解析/切分 -> BGE-M3 Dense/Sparse -> Milvus Hybrid Search + RRF -> Reranker -> 带引用的单轮问答。

当前交付为代码与离线测试完成的开发版本，尚未完成真实模型/存储全链路验收。

已接入句子窗口检索：小单元召回、同章节邻文扩展与合并、窗口精排及完整引用。配置、旧数据兼容和数据库迁移步骤见 [SENTENCE_WINDOWS](docs/SENTENCE_WINDOWS.md)。
范围见 [PHASE1_SCOPE](docs/PHASE1_SCOPE.md)，验证记录见 [VALIDATION](docs/VALIDATION.md)。

已新增 React 工作台：登录、文档列表与上传、任务详情/重试、检索调试、单轮问答和引用展开。
前端启动、同步及边界见 [frontend/README.md](frontend/README.md)。

```bash
# 先启动本文中的 API、Worker 和两个模型服务，再开一个 WSL 终端：
cd /home/aq/vscodeproject/enterprise-support-rag/frontend
npm ci
npm run dev
```

访问 http://localhost:5173；Node.js >=22.12，依赖与 Python 虚拟环境分开。
本次后端增加权限过滤的 `GET /api/v1/documents` 分页接口，前端上线前需要同步后端源码并重建 API。
Windows 开发副本不会自动同步 WSL；仅复制源码和锁文件，保留 WSL 的 .env/models/.venv。

## 1. 使用现有 WSL 环境

WSL 运行目录：`/home/aq/vscodeproject/enterprise-support-rag`。
项目独立虚拟环境：`/home/aq/vscodeproject/enterprise-support-rag/.venv`。
Windows 源码副本位于 `/mnt/c/Users/87936/Desktop/RAG/enterprise-support-rag`，
两份代码不会自动同步；更新源码时保留 WSL 的 `.env`、`.venv` 和 `models`。

```bash
cd /home/aq/vscodeproject/enterprise-support-rag
source .venv/bin/activate
python -m scripts.check_environment
```

已有基础设施：MySQL 8.0、Milvus 2.4.4、Redis、MinIO、etcd。
本项目不重建或升级这些服务，不使用已有 OpenSearch。

新环境按需安装依赖；已安装无需每次重复。不要修改父目录共享虚拟环境。
项目约束 PyMilvus 2.4.x，与 Milvus 2.4.4 对齐，并限制 setuptools<81 兼容 pkg_resources。

```bash
uv pip install --python .venv/bin/python -e ".[dev]"
# WSL 模型服务需要以下依赖；这不是下载模型权重：
uv pip install --python .venv/bin/python -e ".[models]"
```

依赖范围记录在 pyproject.toml。尚未生成经过解析验证的依赖锁文件，部署前应在目标环境锁定版本。

## 2. 配置

复制 `.env.example` 为 `.env`，替换占位值，尤其是：

- JWT_SECRET：至少 32 字符的随机值。
- DATABASE_URL：预先创建的独立数据库 `enterprise_support_rag` 与最小权限账号。
- MinIO 现有凭据；新建项目独立 Bucket `enterprise-support-rag-documents`，不用 Milvus 内部 Bucket。
- MODEL_SERVICE_KEY：API、Worker 与模型服务使用相同内部密钥。
- LLM_BASE_URL、LLM_API_KEY、LLM_MODEL：支持 chat-completions 和 JSON mode 的模型服务。
- EMBEDDING_REVISION/RERANKER_REVISION：验证前固定模型 revision；main 仅为初始占位。
- EMBEDDING_VERSION：改变模型或编码配置时同步变更，并使用新 Collection。
- DEMO_PASSWORD：至少 12 字符，演示脚本不输出密码。

真实密钥不放到截图、日志或 Git。密码中的 URL 特殊字符需要 URL 编码。

### WSL 进程与容器的地址差异

| 服务 | WSL 中运行后端 | 项目 Compose 中运行后端 |
|---|---|---|
| MySQL | localhost:3306 | host.docker.internal:3306 |
| Redis | localhost:6379/6 | milvus-redis:6379/6 |
| Milvus | http://localhost:19530 | http://milvus-standalone:19530 |
| MinIO | 当前容器 IP:9000 或手动映射后的地址 | milvus-minio:9000 |
| 模型服务 | localhost:8001/8002 | WSL 服务地址或同网络 embedding/reranker |

MinIO 现有端口未映射。WSL Linux 主机通常能访问容器桥接 IP，可只读查找：

```bash
docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' milvus-minio
```

IP 可能在重建后变化，仅作为本地开发连接方式。应用容器连接现有 milvus-network 更稳定。
本项目未自动修改端口映射或已有网络。

## 3. 初始化项目数据库与索引

先由数据库管理员创建独立数据库/账号，不将应用账号指向已有业务库。
迁移会创建项目表；bootstrap 只创建指定 Bucket/Collection，不删除已有数据。

```bash
alembic upgrade head
python -m scripts.bootstrap
# seed_demo 读取进程环境中的 DEMO_PASSWORD，交互输入可避免进入命令历史：
read -rsp "Demo password: " DEMO_PASSWORD
export DEMO_PASSWORD
python -m scripts.seed_demo
unset DEMO_PASSWORD
```

创建两个租户 customer-a/customer-b，每个包含 admin 和 reader 账号及一个知识库。
脚本可重复执行，已存在租户不会被覆盖或重置密码。

## 4. 当前启动方案：WSL 模型服务 + Docker API/Worker

| 服务 | 运行位置 | 端口 |
|---|---|---|
| Embedding | WSL 项目虚拟环境，终端一 | 8001 |
| Reranker | WSL 项目虚拟环境，终端二 | 8002 |
| API | Docker Compose | 8000 |
| Celery Worker | Docker Compose | 无 HTTP 端口 |

不要再同时手动启动本地 API 或 Celery，否则会端口冲突或由不同配置的 Worker 竞争消费任务。
已有本地 Celery 请在对应终端 Ctrl+C 正常停止；不要停止两个模型服务。

### 4.1 本地模型和配置

完整模型文件分别放在 `models/bge-m3`、`models/bge-reranker-v2-m3`，
`config.json` 应直接位于对应目录下。保留分词器和模型附属文件，不只复制权重；
若文件是符号链接，确保挂载后仍可解析。模型目录和文件须允许容器用户 UID 10001 读取/遍历。
将 `/models/` 加入 `.gitignore` 和 `.dockerignore`，不提交权重、不打入镜像。

`.env` 中使用以下非敏感配置，实际内部密钥另行填写且保持各服务一致：

```dotenv
EMBEDDING_MODEL=/home/aq/vscodeproject/enterprise-support-rag/models/bge-m3
RERANKER_MODEL=/home/aq/vscodeproject/enterprise-support-rag/models/bge-reranker-v2-m3
MODEL_DEVICE=cpu
MODEL_USE_FP16=false
EMBEDDING_URL=http://127.0.0.1:8001
RERANKER_URL=http://127.0.0.1:8002
COMPOSE_EMBEDDING_URL=http://host.docker.internal:8001
COMPOSE_RERANKER_URL=http://host.docker.internal:8002
```

Worker 切分文档也需要 BGE-M3 分词器。请确认 WSL `compose.yaml` 的 worker
包含以下 environment 和 volumes；替换该服务原有同名配置，不要重复添加 YAML 键。
其余 build、env_file、extra_hosts 和 networks 等配置保留：

```yaml
    environment:
      <<: *app-environment
      EMBEDDING_MODEL: "/models/bge-m3"
      HF_HUB_OFFLINE: "1"
      TRANSFORMERS_OFFLINE: "1"
    volumes:
      - tokenizer-cache:/home/rag/.cache/huggingface
      - type: bind
        source: ./models/bge-m3
        target: /models/bge-m3
        read_only: true
        bind:
          create_host_path: false
```

WSL 路径不会自动出现在容器内。API 只通过 HTTP 调模型，不需要挂载模型目录。

### 4.2 终端一：Embedding

```bash
cd /home/aq/vscodeproject/enterprise-support-rag
source .venv/bin/activate

EMBEDDING_MODEL=/home/aq/vscodeproject/enterprise-support-rag/models/bge-m3 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m uvicorn model_services.embedding.main:app \
  --host 0.0.0.0 --port 8001 --workers 1
```

### 4.3 终端二：Reranker

```bash
cd /home/aq/vscodeproject/enterprise-support-rag
source .venv/bin/activate

RERANKER_MODEL=/home/aq/vscodeproject/enterprise-support-rag/models/bge-reranker-v2-m3 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m uvicorn model_services.reranker.main:app \
  --host 0.0.0.0 --port 8002 --workers 1
```

两个终端保持运行，等待 `Application startup complete`。离线模式下缺文件直接报错，不在线补下载。
监听 0.0.0.0 是为了容器可达；使用防火墙及内部密钥限制访问，不将模型端口暴露到公网。
BGE-M3 输出 1024 维 Dense 和 Sparse；两种模型各使用一个进程，避免重复加载占用内存。
CPU 可用于功能验证；GPU 需另行确认 WSL GPU 和 torch CUDA，不直接假设可用。
Embedding 超长输入明确报错；Reranker 最大长度 2048，仍需评估截断影响。

### 4.4 终端三：API 和 Worker

```bash
cd /home/aq/vscodeproject/enterprise-support-rag
docker compose config --quiet
docker compose up -d api worker
docker compose ps
```

首次部署或修改 Python 源码/依赖后，先执行 `docker compose build api worker`。
只修改 `.env` 或 Compose 挂载时，使用以下命令，无需重建镜像：

```bash
docker compose up -d --force-recreate api worker
```

Compose 需要支持 env_file.required（2.24+），并复用 external milvus-network。
MySQL、Milvus、Redis、MinIO 不由上述命令重建。当前方案不启用 `--profile models`。

## 5. 初始化、验证和故障排查

首次初始化也可以通过 API 镜像执行，避免 WSL 直连 MinIO 的地址差异。
与第 3 节是两种初始化方式，不要求重复执行；已有数据不会被 seed 重置。
schema 升级前停止 API/Worker 写入，执行迁移后再启动：

```bash
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m scripts.bootstrap
docker compose run --rm --no-deps api python -m scripts.seed_demo
```

容器 seed_demo 从 env_file 获取 DEMO_PASSWORD。本地直接执行则需要第 3 节的 export。

启动后，先在 WSL 检查模型服务：

```bash
curl -f http://127.0.0.1:8001/health/live
curl -f http://127.0.0.1:8002/health/live
```

再验证 Worker 的本地分词器、带鉴权的实际模型调用：

```bash
docker compose exec worker python -c 'from transformers import AutoTokenizer; t=AutoTokenizer.from_pretrained("/models/bge-m3", local_files_only=True, use_fast=True); print("分词器加载成功:", type(t).__name__)'
docker compose exec worker python -c 'from app.core.config import get_settings; from app.integrations.embedding_client import EmbeddingClient; r=EmbeddingClient(get_settings()).encode(["连接测试"]); print("编码成功，向量维度:", len(r[0].dense))'
docker compose logs --tail=60 api worker
```

成功编码应输出维度 1024。API healthy 只代表存活，不代表所有外部依赖或问答已通过。

| 现象 | 排查方向 |
|---|---|
| HFValidationError | Worker 模型路径不存在，检查挂载、目录层级和符号链接 |
| EMBEDDING_UNAVAILABLE | 检查模型启动日志、监听地址、容器网络、内部密钥和推理超时 |
| Connection refused | 对应地址没有可达监听服务，先确认模型进程仍在运行 |
| 模型返回 401 / 503 | 检查 MODEL_SERVICE_KEY 是否一致、是否仍是占位符 |
| Redis Authentication required | REDIS_URL / COMPOSE_REDIS_URL 使用现有 Redis 有效凭据 |
| Worker 缺少 PyTorch 警告 | Worker 只用分词器，无需因此安装模型推理库 |
| Celery succeeded，但业务 FAILED | 业务异常已捕获，以任务接口的 READY/FAILED 为准 |
| celery@localhost 与容器节点同时在线 | 停止本地 Celery，避免不同配置竞争任务 |

修复原因后调用 `POST /api/v1/jobs/{job_id}/retry` 重试 FAILED 任务，不必再次上传。
再通过 `GET /api/v1/jobs/{job_id}` 确认 READY。

若以后改用模型容器，需要另外给 embedding/reranker 配置只读模型挂载和容器内路径，
再将 COMPOSE 模型地址改为 http://embedding:8001 和 http://reranker:8002。
不能在目前 WSL 路径配置下直接启用 models profile；也不要与 WSL 模型服务争用相同端口。

## 6. 演示流程

打开 http://localhost:8000/docs：

1. POST /api/v1/auth/login：tenant_name=customer-a，username=admin，输入演示密码。
2. 点击 Authorize 填入返回的 Bearer Token。
3. GET /api/v1/knowledge-bases 获取知识库 ID。
4. POST /api/v1/documents/upload 上传 data/synthetic 中的 Markdown。
5. GET /api/v1/jobs/{job_id} 查看 READY 或明确错误码。
6. POST /api/v1/search 检查候选正文、来源、融合分数和精排分数。
7. POST /api/v1/chat/completions 获取答案、引用和阶段计时。
8. 换 customer-b 身份，验证无法查询 customer-a 的文档或任务。

批量导入三份模拟资料：

```bash
python -m scripts.import_documents --knowledge-base-id YOUR_KB_ID
```

问答请求示例：

```json
{
  "query": "DEMO-DB-001 应该先检查什么？",
  "context": {
    "product_id": "supporthub-demo",
    "product_version": "2.4.1",
    "deployment_mode": "docker_compose"
  }
}
```

所有演示资料均标记 synthetic，不代表真实软件产品规范。

## 7. 测试

```bash
python -m pytest -q
python -m compileall -q app model_services scripts migrations
```

测试使用临时 SQLite、测试 tokenizer 和模型/向量服务替身，不连接生产 MySQL/Milvus。
这些测试验证逻辑与权限，不能代替真实模型质量评估和真实存储联调。

## 8. 第一阶段明确边界

- 完整 JSON 响应；没有 SSE 和完整多轮历史改写。
- 管理员上传并处理成功即发布；完整审核流程尚未实现。
- 基础租户/知识库授权；没有部门/文档 ACL 编辑接口。
- 任务失败可见且可人工重试；Outbox、租约和硬终止自动恢复待实现。
- 上传支持精确去重、请求幂等和显式文档版本更新；删除、版本回滚和索引版本切换 API 待实现。
- OCR 和复杂表格后续补充；扫描页明确失败，不返回空索引。
- 基础结构引用验证不等于事实正确性保证。
- 当前为本地开发配置，没有生产网关限流、SSO 或完整可观测平台。
- .env 及独立账号填好、依赖对齐、模型启动后，才能完成真实端到端验收。

## 9. 上传去重与版本更新

见 [上传身份与版本协议](docs/UPLOAD_VERSIONING.md)。升级前停止 API/Worker 写入，
同步代码并执行 `alembic upgrade head`（新增迁移 0002），再重建、启动应用镜像。
已有文件、任务、分块和向量不会被迁移删除；历史重复文件不会自动合并。
