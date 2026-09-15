from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion[T: Hashable](
    rankings: Sequence[Sequence[T]], k: int = 60, limit: int | None = None
) -> list[T]:
    """Fuse ranked lists: score(d) = Σ 1 / (k + rank_i(d)), rank starting at 1.

    Ties keep the order of first appearance, so results are deterministic.
    """
    scores: dict[T, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    fused = sorted(scores, key=lambda item: scores[item], reverse=True)
    return fused[:limit] if limit is not None else fused
