from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion[T: Hashable](
    rankings: Sequence[Sequence[T]],
    k: int = 60,
    limit: int | None = None,
    weights: Sequence[float] | None = None,
) -> list[T]:
    """Fuse ranked lists: score(d) = Σ w_i / (k + rank_i(d)), rank starting at 1.

    Ties keep the order of first appearance, so results are deterministic.
    """
    if weights is not None and len(weights) != len(rankings):
        raise ValueError("one weight per ranking required")
    scores: dict[T, float] = {}
    for index, ranking in enumerate(rankings):
        weight = weights[index] if weights is not None else 1.0
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + weight / (k + rank)
    fused = sorted(scores, key=lambda item: scores[item], reverse=True)
    return fused[:limit] if limit is not None else fused
