from __future__ import annotations

from typing import Any


def rerank_entries_for_local_subset(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Renumber a filtered leaderboard list from 1..N while preserving order."""
    reranked: list[dict[str, Any]] = []
    for local_rank, raw_entry in enumerate(entries or [], start=1):
        entry = dict(raw_entry or {})
        entry["rank"] = local_rank
        reranked.append(entry)
    return reranked