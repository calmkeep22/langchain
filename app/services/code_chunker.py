from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def chunk_file_content(content: str) -> list[dict]:
    if not content.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, add_start_index=True
    )

    chunks = []
    for index, doc in enumerate(splitter.create_documents([content])):
        start_index = doc.metadata["start_index"]
        start_line = content.count("\n", 0, start_index) + 1
        end_line = start_line + doc.page_content.count("\n")
        chunks.append(
            {
                "chunk_index": index,
                "text": doc.page_content,
                "start_line": start_line,
                "end_line": end_line,
            }
        )
    return chunks


def build_embedding_text(file_path: str, language: str, code: str) -> str:
    return f"File: {file_path}\nLanguage: {language}\n\nCode:\n{code}"
