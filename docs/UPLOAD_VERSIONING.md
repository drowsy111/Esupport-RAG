# 上传身份、精确去重与文档版本

## 接口

沿用 `POST /api/v1/documents/upload`，multipart 新增：

- `document_id`：可选；更新同一租户、同一知识库的指定文档，保持文档 ID，新增 revision。
- `allow_same_name`：默认 false；同名不同内容时，明确选择 true 才另存新文档。
- HTTP `Idempotency-Key`：可选，1～128 字符。建议客户端每次主动上传生成 UUID，网络重试保持不变。

成功响应仍为 HTTP 202，以兼容已有客户端；不代表任务一定在排队。
读取 `status` 获取实时状态；增加 `revision`、`reused`、`replayed`。
重复请求返回原来的文档、版本、任务 ID，不重复投递任务或写入对象。
幂等响应保留原来的资源身份，但状态随任务执行而更新，不是原始 HTTP 字节缓存。

## 判断规则

先校验权限再判断重复。内容身份由租户、知识库、文件类型、原始文件 SHA-256、
product_id/product_version/deployment_mode/source_kind/source_url 共同决定；文件名不参与。
来源元数据也参与，是为了不把不同来源与引用含义的资料静默合并。

同内容、同业务身份的新上传返回已有版本；同名不同内容或元数据返回
DOCUMENT_NAME_CONFLICT（409），用户选择 document_id 更新或 allow_same_name 另存。
allow_same_name 只绕过名称冲突，不绕过内容去重。
显式更新仅对目标文档判断重复，不跳转到其他文档。
历史 SUPERSEDED 版本不作为当前重复结果，因此可以重新上传历史内容形成新修订。
同一文档有 QUEUED/RUNNING/FAILED 任务时，不能再创建另一修订；失败需先重试原任务。
失败版本重复上传返回原失败任务，不自动重试。取消失败版本的接口尚未实现。

请求幂等范围是租户、操作者、知识库。相同键搭配不同文件名、文件内容、元数据、
目标文档或另存选项返回 IDEMPOTENCY_CONFLICT（409）。记录不自动过期。
如果原文档已删除，旧幂等键返回 DOCUMENT_DELETED，不恢复或新建。

## 并发和事务

MySQL 对当前知识库行执行 SELECT FOR UPDATE；等待锁前结束权限查询的旧事务，
获得锁后重新校验权限，避免 REPEATABLE READ 旧快照漏掉刚提交的上传。
upload_claims 和 upload_receipts 使用 SHA-256 主键提供数据库唯一约束兜底。
冲突返回 UPLOAD_CONFLICT（409），客户端使用原键重试后读取已有结果。
同一知识库上传串行，跨知识库可并发；锁覆盖对象上传，首期 10 MB 限制下优先保证一致性。
高并发场景需升级成短事务预留状态与对象上传分离协议。

对象写入失败回滚 SQL；SQL 提交失败尝试回收新对象。进程硬终止仍可能留下孤立对象。
SQL 提交与 Celery 投递之间仍无 Outbox，崩溃窗口和自动恢复是已知限制。

## 发布和检索

旧版继续 PUBLISHED，新版在解析和索引过程中为 DRAFT。
向量 upsert 成功后，一个 SQL 事务把旧版设为 SUPERSEDED、新版设为 PUBLISHED。
新版失败不会改变旧版发布状态。

检索先从 MySQL 获取授权知识库中的已发布 READY 版本 ID，再下推到 Milvus 过滤，
防止旧版/未发布向量抢占 top-k；候选精排前和生成后仍进行权威状态复核。
旧向量和历史分块保留，不主动删除。版本切换恰好发生在检索过程中时可能暂时召回不足，
但旧版候选会被 SQL 复核剔除。大量文档时全量版本 ID 过滤表达式的性能需要专项验证；
后续可改成发布事件、索引同步和可恢复对账协议。

文档详情同时返回最新修订状态和 published_version_id，便于展示“新版失败、旧版仍可用”。
现有检索去重按 document_id + content_hash 处理；跨文档相同段落合并并保留多来源引用尚未实现。
不做语义近似去重，不做跨租户物理存储去重，也不自动清理历史重复记录。

## 升级

Windows 源码和 WSL 运行项目是独立副本，需要同步本次修改的源文件；保留 WSL 的 .env 和 models。
停止应用 API/Worker（包括本地启动的 Worker），保持 MySQL/Milvus/Redis 不动。
在 WSL 项目虚拟环境执行 `alembic upgrade head`，确认 `alembic current` 为 0002。
再执行 `docker compose build api worker` 和 `docker compose up -d api worker`。
如果使用本地 Worker，则重启该进程，不同时启动消费同一队列的旧版 Worker。

迁移只新增两张登记表；旧数据通过首次重复上传时的查询识别，不删除、不改写。
本次测试使用 SQLite 和外部服务替身，验证业务分支及唯一约束；
尚未在用户 MySQL 执行迁移或并发压测，也未在真实 Milvus 验证版本切换。
