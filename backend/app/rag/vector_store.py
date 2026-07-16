import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.config import get_settings

settings = get_settings()

_client = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    return _client


def ensure_collection(collection_name: str):
    client = get_qdrant_client()
    collections = client.get_collections().collections
    existing_names = [c.name for c in collections]
    if collection_name not in existing_names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )


def upsert_chunks(
    collection_name: str,
    chunks: list[dict],
    embeddings: list[list[float]],
):
    client = get_qdrant_client()
    points = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk["text"],
                "page": chunk.get("page", 0),
                "chunk_index": chunk.get("chunk_index", i),
                "source_file": chunk.get("source_file", ""),
            },
        )
        points.append(point)

    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i : i + batch_size]
        client.upsert(collection_name=collection_name, points=batch)


def search(
    collection_name: str,
    query_embedding: list[float],
    top_k: int = 5,
) -> list[dict]:
    client = get_qdrant_client()

    collections = client.get_collections().collections
    existing_names = [c.name for c in collections]
    if collection_name not in existing_names:
        return []

    results = client.search(
        collection_name=collection_name,
        query_vector=query_embedding,
        limit=top_k,
    )

    return [
        {
            "text": hit.payload.get("text", ""),
            "page": hit.payload.get("page", 0),
            "chunk_index": hit.payload.get("chunk_index", 0),
            "source_file": hit.payload.get("source_file", ""),
            "score": hit.score,
        }
        for hit in results
    ]
