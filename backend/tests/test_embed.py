"""Runs the real local model (pre-downloaded in the image); skipped when it is not present."""

from pathlib import Path

import pytest

from app.retrieval.embed import DIM, FastEmbedder

CACHE = Path("/opt/models")


@pytest.mark.skipif(not any(CACHE.glob("*")), reason="embedding model not downloaded")
def test_e5_small_ranks_relevant_passage_first() -> None:
    embedder = FastEmbedder(cache_dir=str(CACHE))
    passages = embedder.embed_passages(
        [
            "Der Vertrag von Rom wurde 1957 unterzeichnet.",
            "Pflanzen gewinnen durch Photosynthese Energie aus Sonnenlicht.",
        ]
    )
    query = embedder.embed_query("Wie nutzen Pflanzen Licht?")

    def score(vector: list[float]) -> float:
        return sum(a * b for a, b in zip(vector, query, strict=True))

    assert len(query) == DIM
    assert score(passages[1]) > score(passages[0])
