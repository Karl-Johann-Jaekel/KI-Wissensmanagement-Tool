"""Local CPU embeddings via fastembed (ADR-02).

Kept free of `app.*` imports so the Dockerfile can run it standalone to pre-download the
model: `python embed.py --download <cache_dir>`.
"""

import sys
import threading
from typing import Any, Protocol

E5_SMALL = "intfloat/multilingual-e5-small"
DIM = 384


class Embedder(Protocol):
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _register_e5_small() -> None:
    """fastembed 0.8 does not ship e5-small; register the official ONNX export."""
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    if any(m["model"] == E5_SMALL for m in TextEmbedding.list_supported_models()):
        return
    TextEmbedding.add_custom_model(
        model=E5_SMALL,
        pooling=PoolingType.MEAN,
        normalization=True,
        sources=ModelSource(hf=E5_SMALL),
        dim=DIM,
        model_file="onnx/model.onnx",
    )


class FastEmbedder:
    def __init__(self, model_name: str = E5_SMALL, cache_dir: str | None = None) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model: Any = None
        self._lock = threading.Lock()
        # e5 models are trained with these prefixes; other models get none
        self._uses_prefixes = "e5" in model_name.lower()

    def _load(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from fastembed import TextEmbedding

                    if self._model_name == E5_SMALL:
                        _register_e5_small()
                    self._model = TextEmbedding(self._model_name, cache_dir=self._cache_dir)
        return self._model

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefix = "passage: " if self._uses_prefixes else ""
        vectors = self._load().embed([prefix + t for t in texts], batch_size=16)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        prefix = "query: " if self._uses_prefixes else ""
        return next(iter(self._load().embed([prefix + text]))).tolist()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--download":
        sys.exit("usage: python embed.py --download <cache_dir>")
    embedder = FastEmbedder(cache_dir=sys.argv[2])
    print("downloaded, dim =", len(embedder.embed_query("warmup")))
