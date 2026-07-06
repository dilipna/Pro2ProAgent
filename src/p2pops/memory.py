"""Semantic memory for discovered ideas -- powers dedupe (skip near-duplicate
problems already seen) via ChromaDB's built-in local embedding model
(all-MiniLM-L6-v2, ONNX, no API key needed).

Cosine distance empirically separates near-duplicate problem statements
(~0.05-0.15) from unrelated ones (~0.9+), so DUPLICATE_DISTANCE_THRESHOLD is
set well below the unrelated range.
"""

from functools import lru_cache
from pathlib import Path

import chromadb

from .config import get_settings

COLLECTION_NAME = "discovered_ideas"
DUPLICATE_DISTANCE_THRESHOLD = 0.3


@lru_cache
def _get_collection():
    settings = get_settings()
    chroma_path = Path(settings.data_dir) / "chroma"
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    return client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def find_duplicate(text: str) -> str | None:
    """Returns the id of an existing near-duplicate idea, or None if `text` is novel."""
    collection = _get_collection()
    if collection.count() == 0:
        return None

    result = collection.query(query_texts=[text], n_results=1)
    distance = result["distances"][0][0]
    if distance < DUPLICATE_DISTANCE_THRESHOLD:
        return result["ids"][0][0]
    return None


def remember(idea_id: str, text: str) -> None:
    """Stores `text`'s embedding under `idea_id` so future ideas can be checked against it."""
    collection = _get_collection()
    collection.add(ids=[idea_id], documents=[text])
