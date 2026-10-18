from app.schemas.chat import EvidenceClaim, GeneratedAnswer
from app.schemas.embedding import EmbeddingItem
from app.schemas.query_plan import QueryPlan


class CharacterTokenizer:
    """Deterministic test tokenizer; never used in production."""
    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(i, i + 1) for i in range(len(text))]}


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, data):
        self.objects[key] = data

    def get(self, key):
        return self.objects[key]

    def remove(self, key):
        del self.objects[key]


class FixedEmbedding:
    def __init__(self):
        self.encoded = []

    def encode(self, texts, kind="documents"):
        self.encoded.append((list(texts), kind))
        return [EmbeddingItem(dense=[1.0] + [0.0] * 1023, sparse={10: 1.0}) for _ in texts]


class MemoryVectors:
    def __init__(self):
        self.rows = {}
        self.include_foreign = False
        self.fail_next = False
        self.search_calls = []

    def upsert(self, rows):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated vector outage")
        self.rows.update({row["id"]: row for row in rows})

    def search(self, embedding, tenant_id, kb_ids, context, published_version_ids=None):
        self.search_calls.append((embedding, tenant_id, list(kb_ids), context))
        return [
            {"id": row["id"], "score": 0.1, "content_hash": row["content_hash"]}
            for row in self.rows.values()
            if self.include_foreign or (
                row["tenant_id"] == tenant_id and row["knowledge_base_id"] in kb_ids
                and (published_version_ids is None or row["version_id"] in published_version_ids)
            )
        ]

    def close(self):
        pass


class RecordingReranker:
    def __init__(self):
        self.seen = []
        self.queries = []

    def score(self, query, texts):
        self.queries.append(query)
        self.seen.extend(texts)
        return [1 / (i + 1) for i in range(len(texts))]


class EvidenceLLM:
    def __init__(self):
        self.calls = []
        self.invalid = False
        self.hook = None
        self.query_plan = QueryPlan(route="direct")
        self.plan_error = None
        self.plan_calls = []

    def plan_query(self, query, history=None, context=None, request_id=None):
        self.plan_calls.append({
            "query": query, "history": history or [], "context": context or {},
            "request_id": request_id,
        })
        if self.plan_error:
            raise self.plan_error
        return self.query_plan

    def generate(self, query, evidence, request_id=None):
        self.calls.append(evidence)
        if self.hook:
            self.hook()
        return GeneratedAnswer(
            status="answered",
            claims=[EvidenceClaim(
                text="请根据已引用资料核对环境条件。",
                citation_ids=["invented" if self.invalid else evidence[0]["id"]],
            )],
        )
