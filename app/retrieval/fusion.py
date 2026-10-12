def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60):
    """Offline reference implementation. Production Milvus performs RRF exactly once."""
    scores = {}
    for ranking in rankings:
        seen = set()
        for rank, identifier in enumerate(ranking, 1):
            if identifier not in seen:
                scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + rank)
                seen.add(identifier)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))

