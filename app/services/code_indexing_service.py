import hashlib
import json
import uuid

from sqlalchemy.orm import Session

from app.core.embeddings import EmbeddingConfigError, get_embeddings
from app.core.errors import ServiceError
from app.core.vector_store import get_code_vector_store
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.code_chunker import build_embedding_text, chunk_file_content
from app.services.code_loader import detect_language, iter_source_files, read_file
from app.services.project_service import get_project


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def index_project_code(
    db: Session, project_id: int, force_reindex: bool = False, embeddings=None
) -> dict:
    project = get_project(db, project_id)

    if embeddings is None:
        try:
            embeddings = get_embeddings()
        except EmbeddingConfigError as exc:
            raise ServiceError("EMBEDDING_FAILED", str(exc), 502) from exc

    vector_store = get_code_vector_store(embeddings)

    indexed_files = 0
    indexed_chunks = 0
    skipped_files = 0

    for file_path in iter_source_files(project.root_path):
        content = read_file(file_path)
        if not content.strip():
            skipped_files += 1
            continue

        relative_path = str(file_path.relative_to(project.root_path)).replace("\\", "/")
        content_hash = _content_hash(content)

        existing_doc = (
            db.query(Document)
            .filter(Document.project_id == project.id, Document.path == relative_path)
            .first()
        )
        if existing_doc and existing_doc.content_hash == content_hash and not force_reindex:
            skipped_files += 1
            continue

        if existing_doc:
            old_chunks = db.query(Chunk).filter(Chunk.document_id == existing_doc.id).all()
            old_vector_ids = [c.vector_id for c in old_chunks]
            if old_vector_ids:
                vector_store.delete(ids=old_vector_ids)
            for c in old_chunks:
                db.delete(c)
            document = existing_doc
            document.content_hash = content_hash
        else:
            document = Document(
                project_id=project.id,
                source_type="code",
                name=file_path.name,
                path=relative_path,
                content_hash=content_hash,
            )
            db.add(document)
            db.flush()

        language = detect_language(file_path)
        chunks = chunk_file_content(content)
        if not chunks:
            skipped_files += 1
            continue

        texts = [build_embedding_text(relative_path, language, c["text"]) for c in chunks]
        metadatas = [
            {
                "source_type": "code",
                "project_id": project.id,
                "file_path": relative_path,
                "language": language,
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "chunk_index": c["chunk_index"],
            }
            for c in chunks
        ]
        vector_ids = [f"{document.id}-{c['chunk_index']}-{uuid.uuid4().hex[:8]}" for c in chunks]

        try:
            vector_store.add_texts(texts=texts, metadatas=metadatas, ids=vector_ids)
        except Exception as exc:
            raise ServiceError("EMBEDDING_FAILED", "Embedding API request failed.", 502) from exc

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

        indexed_files += 1
        indexed_chunks += len(chunks)

    db.commit()

    return {
        "project_id": project.id,
        "indexed_files": indexed_files,
        "indexed_chunks": indexed_chunks,
        "skipped_files": skipped_files,
        "status": "COMPLETED",
    }
