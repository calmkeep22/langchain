import hashlib
import json
import time
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.embeddings import EmbeddingConfigError, get_embeddings
from app.core.errors import ServiceError
from app.core.logging import log_event
from app.core.tree import build_url_tree
from app.core.vector_store import get_docs_vector_store
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.docs_chunker import build_docs_embedding_text, chunk_markdown_content
from app.services.docs_loader import fetch_markdown_pages, read_markdown_file


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load_pages(path: str | None, url: str | None, max_depth: int) -> list[dict]:
    if bool(path) == bool(url):
        raise ServiceError("INVALID_REQUEST", "Exactly one of path or url must be provided.", 400)

    if path:
        file_path = Path(path)
        if not file_path.is_file():
            raise ServiceError("DOCUMENT_PATH_NOT_FOUND", "Document path is invalid.", 400)
        if file_path.suffix != ".md":
            raise ServiceError("UNSUPPORTED_FILE_TYPE", "Only Markdown files are supported.", 400)
        return [{"url": str(file_path), "markdown": read_markdown_file(file_path)}]

    return fetch_markdown_pages(url, max_depth=max_depth)


def index_docs(
    db: Session,
    doc_name: str,
    source_type: str = "official_doc",
    path: str | None = None,
    url: str | None = None,
    max_depth: int = 2,
    force_reindex: bool = False,
    embeddings=None,
) -> dict:
    start = time.perf_counter()
    pages = _load_pages(path, url, max_depth)

    if embeddings is None:
        try:
            embeddings = get_embeddings()
        except EmbeddingConfigError as exc:
            raise ServiceError("EMBEDDING_FAILED", str(exc), 502) from exc

    vector_store = get_docs_vector_store(embeddings)

    indexed_documents = 0
    indexed_chunks = 0
    skipped_documents = 0

    for page in pages:
        content = page["markdown"]
        if not content.strip():
            skipped_documents += 1
            continue

        source = page["url"]
        content_hash = _content_hash(content)

        existing_doc = (
            db.query(Document)
            .filter(
                Document.source_type == source_type,
                Document.name == doc_name,
                Document.path == source,
            )
            .first()
        )
        if existing_doc and existing_doc.content_hash == content_hash and not force_reindex:
            skipped_documents += 1
            continue

        chunks = chunk_markdown_content(content)
        if not chunks:
            skipped_documents += 1
            continue

        is_new_document = existing_doc is None
        if is_new_document:
            document = Document(
                project_id=None,
                source_type=source_type,
                name=doc_name,
                path=source,
                content_hash=content_hash,
            )
            db.add(document)
            db.flush()
        else:
            document = existing_doc

        texts = [build_docs_embedding_text(doc_name, c) for c in chunks]
        metadatas = [
            {
                key: value
                for key, value in {
                    "source_type": source_type,
                    "doc_name": doc_name,
                    "source": source,
                    "h1": c.get("h1"),
                    "h2": c.get("h2"),
                    "h3": c.get("h3"),
                    "chunk_index": c["chunk_index"],
                }.items()
                if value is not None
            }
            for c in chunks
        ]
        vector_ids = [f"{document.id}-{c['chunk_index']}-{uuid.uuid4().hex[:8]}" for c in chunks]

        try:
            vector_store.add_texts(texts=texts, metadatas=metadatas, ids=vector_ids)
        except Exception as exc:
            if is_new_document:
                db.delete(document)
                db.flush()
            raise ServiceError("EMBEDDING_FAILED", "Embedding API request failed.", 502) from exc

        if not is_new_document:
            old_chunks = db.query(Chunk).filter(Chunk.document_id == document.id).all()
            old_vector_ids = [c.vector_id for c in old_chunks]
            if old_vector_ids:
                vector_store.delete(ids=old_vector_ids)
            for c in old_chunks:
                db.delete(c)
            document.content_hash = content_hash

        for c, meta, vector_id in zip(chunks, metadatas, vector_ids):
            db.add(
                Chunk(
                    document_id=document.id,
                    vector_id=vector_id,
                    chunk_index=c["chunk_index"],
                    content_preview=c["text"][:200],
                    metadata_json=json.dumps(meta),
                )
            )

        indexed_documents += 1
        indexed_chunks += len(chunks)

    db.commit()

    page_tree = build_url_tree([p["url"] for p in pages]) if url else None

    latency_ms = int((time.perf_counter() - start) * 1000)
    log_event(
        "docs_indexing_completed",
        doc_name=doc_name,
        indexed_documents=indexed_documents,
        indexed_chunks=indexed_chunks,
        skipped_documents=skipped_documents,
        page_tree=page_tree,
        latency_ms=latency_ms,
    )

    return {
        "doc_name": doc_name,
        "indexed_documents": indexed_documents,
        "indexed_chunks": indexed_chunks,
        "skipped_documents": skipped_documents,
        "status": "COMPLETED",
        "page_tree": page_tree,
    }
