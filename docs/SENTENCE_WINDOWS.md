# 句子窗口检索

新上传文档使用 `sentence-v1` 切分。中文句末标点、英文句末句点与换行作为候选边界；常见英文缩写、版本号和 URL 内部句点保留。列表项、表格行和代码围栏优先保持完整，超长单元按 BGE Token 上限无重叠切分。这里采用确定性规则，不是通用自然语言句法分析器。

流程：小单元向量召回 → SQL 授权与正文核验 → 同章节邻文扩展 → 重叠窗口合并 → 标题和完整窗口一次精排 → Top-K → evidence → LLM。

## 配置

| 配置 | 默认值 | 含义 |
|---|---|---|
| SENTENCE_MAX_TOKENS | 200 | 单个检索单元 Token 上限，不是目标长度 |
| WINDOW_NEIGHBORS | 2 | 每侧最多扩展两个单元 |
| WINDOW_MAX_TOKENS | 800 | 持久化 BGE Token 数加分隔符预留的窗口预算 |
| CONTEXT_TOP_K | 8 | 窗口精排后最多返回数量 |
| CONTEXT_CHAR_BUDGET | 16000 | evidence JSON 字符预算 |

窗口预算不是目标 LLM 的精确 Token 数。当前 LLM 提供商可配置，未引入未经验证的统一 tokenizer；输入仍需结合实际模型上下文长度配置。旧 CHUNK_MAX_TOKENS / CHUNK_OVERLAP_TOKENS 仅保留旧切分函数及兼容配置，新导入走 SENTENCE_MAX_TOKENS。

## 边界、合并和引用

- 窗口不得跨文档、版本、章节；PDF 暂时不得跨页。重复同名标题也建立新章节。
- 同章节的短段落可以跨 block 扩展，避免仍被短结构块限制。缺失或无权限的邻居会终止该方向扩展。
- 合并重叠窗口时按原文顺序排列，使用最大召回分数，只有合并后仍满足预算才合并。预算不允许时可能保留部分重叠窗口。
- `text` 和引用 `quote` 是完整窗口；`matched_text` 与原 `chunk_id/page/anchor` 对应代表性命中核心；`matched_chunk_ids` 保存合并后的所有命中 ID。
- `sources` 保存窗口全部组成单元的文本、页码、锚点、哈希和结构位置，可逐段定位。
- 发送 LLM 前和生成后，重新校验所有组成单元的权限、版本、文本及元数据；任一失效将丢弃整个窗口。
- SQL `chunks.structure` 保存 strategy、section、block 和清洗后结构块内字符起止位置；Milvus schema 不变。

## 升级

当前 Windows 源码副本不会自动同步到 README 中的 WSL 运行目录。先同步源码（保留运行环境的 .env、.venv、models），停止 API / Worker，在目标项目环境执行：

```bash
alembic upgrade head
```

该操作应用 `0003_sentence_windows`，只给 chunks 增加可空 JSON 列，不重写旧 Chunk。迁移后重建/重启 API 和 Worker，前端重新构建。无需删除 Milvus Collection。

旧记录 structure 为 NULL，继续返回原始 Chunk，不推断不可靠的句子位置。新导入的文档使用句子窗口。已有文档要获得新切分需要专门重处理；本次没有批量重写生产数据，也没有提供 READY 文档的一键重处理任务。原文件重复上传会被现有幂等逻辑复用，不能把重复上传当作重新切分方法。

## 验证范围

单元和离线集成测试覆盖技术文本保留、Token 兜底、窗口预算、重叠合并、重复标题、PDF 页边界、旧数据、越权邻文、生成期间文本修改和版本失效。测试使用 SQLite 和模型替身；真实 MySQL / Milvus / BGE 服务效果需在部署环境用代表性问题验收。
