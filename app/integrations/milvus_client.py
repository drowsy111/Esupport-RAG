from app.core.exceptions import AppError
from app.indexing.collection_schema import create_collection
from app.retrieval.filters import build_filter, literal


class VectorStore:
    def __init__(self, settings):
        from pymilvus import MilvusClient
        self.settings = settings
        self.collection = settings.milvus_collection
        self.client = MilvusClient(uri=settings.milvus_uri, timeout=30)

    def initialize(self):
        create_collection(self.client, self.collection)
        self.client.load_collection(self.collection)

    def upsert(self, rows):
        try:
            for offset in range(0, len(rows), 100):
                self.client.upsert(collection_name=self.collection, data=rows[offset:offset + 100])
        except Exception as exc:
            raise AppError("INDEX_WRITE_FAILED", "检索索引写入失败", 503) from exc

    def search(self, embedding, tenant_id, kb_ids, context, published_version_ids=None):
        from pymilvus import AnnSearchRequest, RRFRanker
        if not kb_ids:
            return []
        if published_version_ids == []:
            return []
        expr = build_filter(tenant_id, kb_ids, context, self.settings.embedding_version)
        if published_version_ids is not None:
            expr += f" and version_id in {literal(published_version_ids)}"
        requests = [
            AnnSearchRequest(
                data=[embedding.dense], anns_field="dense_vector",
                param={"metric_type": "COSINE", "params": {"ef": 256}},
                limit=self.settings.dense_top_k, expr=expr,
            ),
        ]
        if embedding.sparse:
            requests.append(AnnSearchRequest(
                data=[embedding.sparse], anns_field="sparse_vector",
                param={"metric_type": "IP", "params": {}},
                limit=self.settings.sparse_top_k, expr=expr,
            ))
        try:
            result = self.client.hybrid_search(
                collection_name=self.collection, reqs=requests, ranker=RRFRanker(k=60),
                limit=self.settings.fusion_top_k,
                output_fields=["content_hash"], consistency_level="Strong",
            )
            return [
                {"id": str(hit["id"]), "score": float(hit["distance"]),
                 "content_hash": hit["entity"]["content_hash"]}
                for hit in result[0]
            ]
        except Exception as exc:
            raise AppError("SEARCH_UNAVAILABLE", "混合检索暂不可用", 503) from exc

    def close(self):
        self.client.close()
