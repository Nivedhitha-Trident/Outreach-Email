import uuid
import chromadb
from chromadb.config import Settings
from config.settings import COLLECTIONS, TOP_K_RESULTS
from services.llm_service import embed_texts, embed_query

_client = None
_collections = {}


def get_chroma_client() -> chromadb.EphemeralClient:
    global _client
    if _client is None:
        _client = chromadb.EphemeralClient(
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str):
    global _collections
    if name not in _collections:
        client = get_chroma_client()
        _collections[name] = client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collections[name]


def add_documents(
    collection_name: str,
    texts: list[str],
    metadatas: list[dict] = None,
    ids: list[str] = None,
) -> list[str]:
    if not texts:
        return []

    collection = get_collection(collection_name)
    if ids is None:
        ids = [str(uuid.uuid4()) for _ in texts]
    if metadatas is None:
        metadatas = [{} for _ in texts]

    embeddings = embed_texts(texts)
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return ids


def upsert_document(
    collection_name: str,
    text: str,
    metadata: dict = None,
    doc_id: str = None,
) -> str:
    collection = get_collection(collection_name)
    if doc_id is None:
        doc_id = str(uuid.uuid4())
    if metadata is None:
        metadata = {}

    embedding = embed_query(text)
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
    )
    return doc_id


def semantic_search(
    collection_name: str,
    query: str,
    n_results: int = TOP_K_RESULTS,
    where: dict = None,
) -> list[dict]:
    collection = get_collection(collection_name)
    count = collection.count()
    if count == 0:
        return []

    n_results = min(n_results, count)
    query_embedding = embed_query(query)

    kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text": doc,
                "metadata": meta,
                "relevance": round(1 - dist, 4),
            })
    return output


def multi_collection_search(
    query: str,
    collections: list[str],
    n_per_collection: int = 3,
) -> list[dict]:
    all_results = []
    for cname in collections:
        results = semantic_search(cname, query, n_results=n_per_collection)
        for r in results:
            r["collection"] = cname
        all_results.extend(results)
    all_results.sort(key=lambda x: x["relevance"], reverse=True)
    return all_results


def get_collection_stats() -> dict:
    stats = {}
    for name in COLLECTIONS.values():
        try:
            col = get_collection(name)
            stats[name] = col.count()
        except Exception:
            stats[name] = 0
    return stats


def clear_all_collections():
    global _collections
    client = get_chroma_client()
    for name in COLLECTIONS.values():
        try:
            col = client.get_or_create_collection(name)
            ids = col.get()["ids"]
            if ids:
                col.delete(ids=ids)
        except Exception:
            pass
    _collections = {}


def delete_document(collection_name: str, doc_id: str):
    collection = get_collection(collection_name)
    collection.delete(ids=[doc_id])


def get_document(collection_name: str, doc_id: str) -> dict | None:
    collection = get_collection(collection_name)
    result = collection.get(ids=[doc_id], include=["documents", "metadatas"])
    if result["documents"]:
        return {"text": result["documents"][0], "metadata": result["metadatas"][0]}
    return None


def format_search_results_as_context(results: list[dict], max_tokens: int = 3000) -> str:
    if not results:
        return "No relevant context found."
    context_parts = []
    total_chars = 0
    char_limit = max_tokens * 4
    for i, r in enumerate(results, 1):
        source = r.get("metadata", {}).get("source", r.get("collection", "knowledge base"))
        text = r["text"]
        relevance = r.get("relevance", 0)
        part = f"[Source {i}: {source} | Relevance: {relevance:.2f}]\n{text}"
        if total_chars + len(part) > char_limit:
            break
        context_parts.append(part)
        total_chars += len(part)
    return "\n\n---\n\n".join(context_parts)
