from dataclasses import dataclass
from typing import Any


@dataclass
class Resources:
    storage: Any
    embedding: Any
    reranker: Any
    vectors: Any
    llm: Any
    dispatch: Any

    @classmethod
    def production(cls, settings):
        from app.integrations.embedding_client import EmbeddingClient
        from app.integrations.llm_gateway import LLMGateway
        from app.integrations.milvus_client import VectorStore
        from app.integrations.object_storage import ObjectStorage
        from app.integrations.reranker_client import RerankerClient

        def dispatch(job_id):
            from app.workers.tasks import ingest_document
            ingest_document.apply_async(args=[job_id], queue="ingestion")

        return cls(
            ObjectStorage(settings), EmbeddingClient(settings), RerankerClient(settings),
            VectorStore(settings), LLMGateway(settings), dispatch,
        )

    def close(self):
        self.vectors.close()

