"""Lightweight ChromaDB RAG service for portfolio evidence."""

from __future__ import annotations
import logging
import hashlib
import math
import re
from typing import Any
import chromadb
from app.config import settings
from app.services.portfolio_parser import parse_file

logger = logging.getLogger(__name__)
COLLECTION_NAME = "portfolio"
_client = None
EMBEDDING_DIMENSIONS = 384


def embed_text(text: str) -> list[float]:
    """Offline-safe hashed token embedding; deterministic and dependency-free."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % EMBEDDING_DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client


def get_portfolio_collection():
    return get_chroma_client().get_or_create_collection(name=COLLECTION_NAME, embedding_function=None)


def chunk_text(text: str, chunk_size: int = 120, overlap: int = 20) -> list[str]:
    """Split on words, keeping a small overlap so evidence retains context."""
    words = text.split()
    if not words:
        return []
    step = max(1, chunk_size - overlap)
    return [" ".join(words[start:start + chunk_size]) for start in range(0, len(words), step)]


def ingest_portfolio_item(item_id: str, file_paths: list[str]) -> None:
    documents, metadatas, ids = [], [], []
    index = 0
    for file_path in file_paths:
        try:
            text = parse_file(file_path)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("Skipping %s: %s", file_path, exc)
            continue
        for chunk in chunk_text(text):
            documents.append(chunk)
            metadatas.append({"item_id": item_id, "chunk_index": index})
            ids.append(f"{item_id}_{index}")
            index += 1
    if documents:
        embeddings = [embed_text(document) for document in documents]
        get_portfolio_collection().upsert(
            documents=documents, embeddings=embeddings, metadatas=metadatas, ids=ids
        )


def query_portfolio(query: str, top_k: int = 2, item_id_filter: str | None = None) -> list[dict]:
    if not query.strip() or top_k <= 0:
        return []
    collection = get_portfolio_collection()
    if collection.count() == 0:
        return []
    kwargs: dict[str, Any] = {
        "query_embeddings": [embed_text(query)], "n_results": min(top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if item_id_filter:
        kwargs["where"] = {"item_id": item_id_filter}
    results = collection.query(**kwargs)
    return [
        {"document": doc, "metadata": meta, "distance": distance}
        for doc, meta, distance in zip(
            results.get("documents", [[]])[0], results.get("metadatas", [[]])[0],
            results.get("distances", [[]])[0]
        )
    ]


def format_evidence_for_agent(results: list[dict]) -> str:
    lines = []
    for result in results[:2]:
        text = " ".join(str(result.get("document", "")).split())[:450]
        item_id = (result.get("metadata") or {}).get("item_id", "portfolio")
        if text:
            lines.append(f"- Portfolio item {item_id}: {text}")
    return "\n".join(lines)


__all__ = ["chunk_text", "ingest_portfolio_item", "query_portfolio", "format_evidence_for_agent", "get_chroma_client"]
