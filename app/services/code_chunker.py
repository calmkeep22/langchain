import ast

from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
MAX_SYMBOL_CHUNK_SIZE = 4000


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
                "chunk_type": "block",
                "symbol_name": None,
                "parent_symbol": None,
                "parent_start_line": None,
                "parent_end_line": None,
            }
        )
    return chunks


def _decorated_start_line(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", [])
    if decorators:
        return min(d.lineno for d in decorators)
    return node.lineno


def _node_text(lines: list[str], start_line: int, end_line: int) -> str:
    return "\n".join(lines[start_line - 1 : end_line])


def _split_if_too_long(lines: list[str], chunk: dict) -> list[dict]:
    if len(chunk["text"]) <= MAX_SYMBOL_CHUNK_SIZE:
        return [chunk]

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, add_start_index=True
    )
    sub_chunks = []
    for doc in splitter.create_documents([chunk["text"]]):
        start_index = doc.metadata["start_index"]
        offset = chunk["text"].count("\n", 0, start_index)
        start_line = chunk["start_line"] + offset
        end_line = start_line + doc.page_content.count("\n")
        sub_chunks.append(
            {
                **chunk,
                "text": doc.page_content,
                "start_line": start_line,
                "end_line": end_line,
            }
        )
    return sub_chunks


def chunk_python_ast(content: str) -> list[dict] | None:
    """AST-based chunking: one chunk per top-level function and per method.

    Falls back to ``None`` (caller should use ``chunk_file_content``) on a
    syntax error, so a single unparsable file doesn't break indexing.
    Methods carry their class as ``parent_symbol``/``parent_start_line``/
    ``parent_end_line`` so a reviewer can later expand a small matched chunk
    (a method) out to its full class for more context (Small-to-Big).
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    lines = content.splitlines()
    raw_chunks: list[dict] = []
    covered_lines: set[int] = set()

    def add_chunk(
        node: ast.AST,
        chunk_type: str,
        symbol_name: str,
        parent_symbol: str | None = None,
        parent_start_line: int | None = None,
        parent_end_line: int | None = None,
    ) -> None:
        start_line = _decorated_start_line(node)
        end_line = node.end_lineno
        text = _node_text(lines, start_line, end_line)
        if not text.strip():
            return
        raw_chunks.append(
            {
                "text": text,
                "start_line": start_line,
                "end_line": end_line,
                "chunk_type": chunk_type,
                "symbol_name": symbol_name,
                "parent_symbol": parent_symbol,
                "parent_start_line": parent_start_line,
                "parent_end_line": parent_end_line,
            }
        )
        covered_lines.update(range(start_line, end_line + 1))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_chunk(node, "function", node.name)
        elif isinstance(node, ast.ClassDef):
            methods = [
                child
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if not methods:
                add_chunk(node, "class", node.name)
                continue
            for method in methods:
                add_chunk(
                    method,
                    "method",
                    f"{node.name}.{method.name}",
                    parent_symbol=node.name,
                    parent_start_line=node.lineno,
                    parent_end_line=node.end_lineno,
                )

    raw_chunks.extend(_gap_chunks(lines, covered_lines))
    raw_chunks.sort(key=lambda c: c["start_line"])

    chunks: list[dict] = []
    chunk_index = 0
    for raw_chunk in raw_chunks:
        for sub_chunk in _split_if_too_long(lines, raw_chunk):
            chunks.append({**sub_chunk, "chunk_index": chunk_index})
            chunk_index += 1

    return chunks


def _gap_chunks(lines: list[str], covered_lines: set[int]) -> list[dict]:
    """Module-level code not covered by any function/class (imports, etc.)."""
    total_lines = len(lines)
    gaps: list[tuple[int, int]] = []
    start = None
    for i in range(1, total_lines + 1):
        if i not in covered_lines:
            if start is None:
                start = i
        elif start is not None:
            gaps.append((start, i - 1))
            start = None
    if start is not None:
        gaps.append((start, total_lines))

    chunks = []
    for gap_start, gap_end in gaps:
        text = "\n".join(lines[gap_start - 1 : gap_end])
        if not text.strip():
            continue
        chunks.append(
            {
                "text": text,
                "start_line": gap_start,
                "end_line": gap_end,
                "chunk_type": "module",
                "symbol_name": None,
                "parent_symbol": None,
                "parent_start_line": None,
                "parent_end_line": None,
            }
        )
    return chunks


def build_embedding_text(
    file_path: str,
    language: str,
    code: str,
    *,
    chunk_type: str | None = None,
    symbol_name: str | None = None,
    parent_symbol: str | None = None,
) -> str:
    parts = [f"File: {file_path}", f"Language: {language}"]
    if chunk_type:
        parts.append(f"Type: {chunk_type}")
    if symbol_name:
        parts.append(f"Symbol: {symbol_name}")
    if parent_symbol:
        parts.append(f"Parent: {parent_symbol}")
    parts.extend(["", "Code:", code])
    return "\n".join(parts)
