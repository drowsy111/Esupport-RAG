from pathlib import Path
from threading import Lock


class Scorer:
    def __init__(self, settings):
        from FlagEmbedding import FlagReranker
        from huggingface_hub import snapshot_download
        model_path = settings.reranker_model
        if not Path(model_path).is_dir():
            model_path = snapshot_download(model_path, revision=settings.reranker_revision)
        self.model = FlagReranker(
            model_path, use_fp16=settings.model_use_fp16, devices=settings.model_device,
            max_length=2048,
        )
        self.lock = Lock()

    def score(self, query, texts):
        with self.lock:
            scores = self.model.compute_score(
                [[query, text] for text in texts], batch_size=8, normalize=True,
            )
        if isinstance(scores, (float, int)):
            scores = [scores]
        return [float(score) for score in scores]

