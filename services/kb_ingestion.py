import uuid
from config.settings import COLLECTIONS, CHUNK_SIZE, CHUNK_OVERLAP
from services.chroma_manager import add_documents
from store import save_kb_document
from utils.document_processor import (
    extract_text_from_file, chunk_text_recursive, clean_text, get_file_type_label
)


COLLECTION_BY_DOC_TYPE = {
    "solution": COLLECTIONS["solutions_kb"],
    "case_study": COLLECTIONS["case_studies"],
    "industry": COLLECTIONS["industry_knowledge"],
    "general": COLLECTIONS["solutions_kb"],
}


def ingest_document(
    file_bytes: bytes,
    filename: str,
    doc_type: str = "general",
    custom_metadata: dict = None,
) -> dict:
    try:
        raw_text = extract_text_from_file(file_bytes, filename)
        raw_text = clean_text(raw_text)
    except Exception as e:
        return {"success": False, "error": f"Text extraction failed: {e}"}

    if len(raw_text.strip()) < 100:
        return {"success": False, "error": "Document appears empty or too short."}

    chunks = chunk_text_recursive(raw_text, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    if not chunks:
        return {"success": False, "error": "No usable content after chunking."}

    doc_id = str(uuid.uuid4())
    collection_name = COLLECTION_BY_DOC_TYPE.get(doc_type, COLLECTIONS["solutions_kb"])

    base_metadata = {
        "source": filename,
        "doc_id": doc_id,
        "doc_type": doc_type,
        "file_type": get_file_type_label(filename),
        "chunk_total": len(chunks),
    }
    if custom_metadata:
        base_metadata.update(custom_metadata)

    chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{**base_metadata, "chunk_index": i} for i in range(len(chunks))]

    try:
        add_documents(
            collection_name=collection_name,
            texts=chunks,
            metadatas=metadatas,
            ids=chunk_ids,
        )
    except Exception as e:
        return {"success": False, "error": f"ChromaDB storage failed: {e}"}

    save_kb_document(
        doc_id=doc_id,
        filename=filename,
        doc_type=doc_type,
        collection=collection_name,
        chunk_count=len(chunks),
        metadata=base_metadata,
    )

    return {
        "success": True,
        "doc_id": doc_id,
        "filename": filename,
        "doc_type": doc_type,
        "chunk_count": len(chunks),
        "collection": collection_name,
        "text_length": len(raw_text),
    }


def ingest_text_note(
    title: str,
    content: str,
    doc_type: str = "general",
    metadata: dict = None,
) -> dict:
    content = clean_text(content)
    if len(content) < 50:
        return {"success": False, "error": "Content too short."}

    chunks = chunk_text_recursive(content, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    doc_id = str(uuid.uuid4())
    collection_name = COLLECTION_BY_DOC_TYPE.get(doc_type, COLLECTIONS["solutions_kb"])

    base_metadata = {
        "source": title,
        "doc_id": doc_id,
        "doc_type": doc_type,
        "file_type": "Text Note",
        "chunk_total": len(chunks),
        **(metadata or {}),
    }

    chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{**base_metadata, "chunk_index": i} for i in range(len(chunks))]

    add_documents(
        collection_name=collection_name,
        texts=chunks,
        metadatas=metadatas,
        ids=chunk_ids,
    )

    save_kb_document(
        doc_id=doc_id,
        filename=title,
        doc_type=doc_type,
        collection=collection_name,
        chunk_count=len(chunks),
        metadata=base_metadata,
    )

    return {
        "success": True,
        "doc_id": doc_id,
        "title": title,
        "chunk_count": len(chunks),
        "collection": collection_name,
    }


def ingest_batch(files: list[tuple[bytes, str, str]]) -> list[dict]:
    results = []
    for file_bytes, filename, doc_type in files:
        result = ingest_document(file_bytes, filename, doc_type)
        results.append(result)
    return results


def seed_trident_kb() -> bool:
    """Seed the itTrident built-in knowledge base on first run. Idempotent."""
    from config.knowledge_base import TRIDENT_KB, TRIDENT_KB_DOC_ID, TRIDENT_KB_TITLE
    from services.chroma_manager import get_document

    sentinel_id = f"{TRIDENT_KB_DOC_ID}_chunk_0"
    if get_document(COLLECTIONS["solutions_kb"], sentinel_id) is not None:
        return False

    content = clean_text(TRIDENT_KB)
    chunks = chunk_text_recursive(content, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    base_metadata = {
        "source": TRIDENT_KB_TITLE,
        "doc_id": TRIDENT_KB_DOC_ID,
        "doc_type": "solution",
        "file_type": "Built-in",
        "chunk_total": len(chunks),
    }
    chunk_ids = [f"{TRIDENT_KB_DOC_ID}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{**base_metadata, "chunk_index": i} for i in range(len(chunks))]

    add_documents(
        collection_name=COLLECTIONS["solutions_kb"],
        texts=chunks,
        metadatas=metadatas,
        ids=chunk_ids,
    )
    save_kb_document(
        doc_id=TRIDENT_KB_DOC_ID,
        filename=TRIDENT_KB_TITLE,
        doc_type="solution",
        collection=COLLECTIONS["solutions_kb"],
        chunk_count=len(chunks),
        metadata=base_metadata,
    )
    return True
