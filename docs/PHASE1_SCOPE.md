# 第一阶段交付范围

## 已写入的实现

- FastAPI 登录、知识库列表、上传、任务查询/重试、检索、单轮问答接口。
- MySQL ORM 与 Alembic 初始迁移；演示租户和基础知识库权限。
- MinIO 原文存储；Celery 异步摄取；显式任务阶段与错误码。
- Markdown、DOCX、文本 PDF 解析；BGE tokenizer 切分与原文位置。
- BGE-M3 Dense/Sparse 服务、Milvus 2.4 系列客户端、一次 RRF 融合。
- 可配置 Reranker，初始候选型号 BAAI/bge-reranker-v2-m3。
- 基于证据的 JSON 回答、服务端引用、无证据拒答和基础升级追问。
- 会话消息保存、检索阶段计时；会话历史目前不参与下一轮生成。
- 应用 Compose 复用已有 WSL 基础设施，不包含数据库重建或升级动作。

## 明确的首期限制

1. 管理员上传被视为确认发布，只有处理成功后权威状态才变为 PUBLISHED；完整审核流程待实现。
2. 文件哈希同时用于完整性检查和知识库内精确去重；上传支持 Idempotency-Key，任务重试使用稳定 Chunk ID。
3. 上传指定 document_id 可创建下一修订，新版成功才替换已发布版本；删除、版本回滚和索引版本发布尚未实现。详见 UPLOAD_VERSIONING.md。
4. 软件适用性目前支持明确的产品/版本/部署方式精确匹配与空值通用资料，不解释复杂版本范围。
5. PDF 无文本页（包括混合扫描页或空白页）返回 OCR_REQUIRED；OCR 尚未实现。
6. DOCX 不推断页码，使用正文块锚点；表格仅保留基础行列文本。
7. Chunk 按现有结构块切分，大块按 Token 兜底；未合并所有相邻小段落，不宣称最优检索效果。
8. Broker 投递与 MySQL 不在同一事务；有 FAILED 重试，完整 Outbox 和自动对账仍待实现。
9. Worker 硬终止可能留下 RUNNING；不得直接盲重试，需确认无旧 Worker 后人工恢复。租约和自动恢复待实现。
10. 引用校验确认 ID、权限和原文定位，不证明每个结论语义上正确。
11. 回答为完成校验后的完整 JSON，无实时 Token 流。
12. 无完整 ACL、自动评估平台、Prometheus/Grafana 看板或自动重建。
13. 上下文使用字符预算近似限制；不同 LLM 的实际 Token 预算需要模型适配。
14. 默认不使用已有 OpenSearch；混合召回为 BGE-M3 Dense + Sparse。
15. 真实模型服务会加载/下载大模型；未配置或不可用时明确报错，不自动替换成假向量。

## 数据隔离边界

租户来自服务器验证的 Token 和当前账号。知识库授权同时用于向量过滤和 MySQL 候选复核；候选在精排前校验，生成后再次检查。读取使用新事务避免重复读快照保留过期授权。首期没有实时撤权 API，检查与返回之间的并发授权变更仍需在后续权限版本协议中进一步处理。

数据库保存的消息包含授权回答与引用，属于业务数据；尚未开放历史消息读取接口，不能在以后添加接口时跳过当前授权复核。

## WSL 环境观察

用户指定环境：/home/aq/vscodeproject/.venv。
已运行 MySQL 8.0、Milvus 2.4.4、Redis、MinIO、etcd。
已安装 PyMilvus 3.0.2；项目声明 2.4 系列以与现有服务端匹配，尚未变更共享环境。
WSL 环境缺少 FastAPI、Celery、MinIO SDK、PyJWT、python-multipart、Alembic 和 pytest 等。
代码写入不代表这些服务已联调成功；最终验证结果见 VALIDATION.md。
