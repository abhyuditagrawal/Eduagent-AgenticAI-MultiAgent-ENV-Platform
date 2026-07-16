from app.rag.embeddings import embed_query
from app.rag.vector_store import search


def retrieve(query: str, subject_code: str, top_k: int = 5) -> list[dict]:
    collection_name = f"subject_{subject_code.lower()}"
    query_embedding = embed_query(query)
    results = search(collection_name, query_embedding, top_k=top_k)
    return results
