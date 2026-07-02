from langchain_chroma import Chroma

from app.core.config import get_settings


def get_code_vector_store(embeddings) -> Chroma:
    settings = get_settings()
    return Chroma(
        collection_name="code_chunks",
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


def get_docs_vector_store(embeddings) -> Chroma:
    settings = get_settings()
    return Chroma(
        collection_name="official_docs_chunks",
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )
