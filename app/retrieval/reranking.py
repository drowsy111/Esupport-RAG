def rerank(query, candidates, client, top_k):
    if not candidates:
        return []
    scores = client.score(query, [
        f"{c.title_path}\n{c.text}" if c.title_path else c.text for c in candidates
    ])
    for candidate, score in zip(candidates, scores, strict=True):
        candidate.rerank_score = score
    return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]

