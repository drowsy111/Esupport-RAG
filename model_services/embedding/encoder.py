from threading import Lock

from app.schemas.embedding import EmbeddingItem


class Encoder:
    def __init__(self, settings):
        from FlagEmbedding import BGEM3FlagModel
        from huggingface_hub import snapshot_download
        from pathlib import Path

        model_path = settings.embedding_model
        if not Path(model_path).is_dir():
            model_path = snapshot_download(model_path, revision=settings.embedding_revision)
        self.model = BGEM3FlagModel(
            model_path, use_fp16=settings.model_use_fp16, devices=settings.model_device,
            normalize_embeddings=True,
        )
        self.settings = settings
        self.lock = Lock()

    def encode(self, texts):
        for text in texts:
            if len(self.model.tokenizer.encode(text, add_special_tokens=True)) > (
                self.settings.embedding_max_length
            ):
                raise ValueError("Input exceeds embedding token limit; no silent truncation")
        with self.lock:
            result = self.model.encode(
                texts, batch_size=8, max_length=self.settings.embedding_max_length,
                return_dense=True, return_sparse=True, return_colbert_vecs=False,
            )
        return [
            EmbeddingItem(dense=dense.tolist(),
                          sparse={int(k): float(v) for k, v in sparse.items()})
            for dense, sparse in zip(result["dense_vecs"], result["lexical_weights"], strict=True)
        ]

