from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

HEADERS_TO_SPLIT_ON = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def chunk_markdown_content(markdown: str) -> list[dict]:
    if not markdown.strip():
        return []

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON, strip_headers=False
    )
    sections = header_splitter.split_text(markdown)
    if not sections:
        return []

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )

    chunks = []
    chunk_index = 0
    for section in sections:
        for sub_text in text_splitter.split_text(section.page_content):
            if not sub_text.strip():
                continue
            chunks.append(
                {
                    "chunk_index": chunk_index,
                    "text": sub_text,
                    "h1": section.metadata.get("h1"),
                    "h2": section.metadata.get("h2"),
                    "h3": section.metadata.get("h3"),
                }
            )
            chunk_index += 1

    return chunks


def build_docs_embedding_text(doc_name: str, chunk: dict) -> str:
    section_parts = [part for part in (chunk.get("h1"), chunk.get("h2"), chunk.get("h3")) if part]
    header = f"Document: {doc_name}"
    if section_parts:
        header += f"\nSection: {' > '.join(section_parts)}"
    return f"{header}\n\nContent:\n{chunk['text']}"
