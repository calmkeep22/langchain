import re

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.db.session import engine

# Two alternatives instead of one [\w가-힣]+ class: Python's \w already
# matches Hangul, so a single class glues a Korean particle directly onto a
# preceding identifier (e.g. "response_model이랑" -> one unmatchable token).
# Splitting per script keeps "response_model" searchable on its own.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[가-힣]+")


def ensure_fts_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            sql_text(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5("
                "chunk_id UNINDEXED, project_id UNINDEXED, source_type UNINDEXED, "
                "file_path, symbol_name, content)"
            )
        )


def index_fts_rows(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    for row in rows:
        db.execute(
            sql_text(
                "INSERT INTO chunk_fts (chunk_id, project_id, source_type, file_path, symbol_name, content) "
                "VALUES (:chunk_id, :project_id, :source_type, :file_path, :symbol_name, :content)"
            ),
            row,
        )


def delete_fts_rows(db: Session, chunk_ids: list[int]) -> None:
    if not chunk_ids:
        return
    placeholders = ",".join(str(int(i)) for i in chunk_ids)
    db.execute(sql_text(f"DELETE FROM chunk_fts WHERE chunk_id IN ({placeholders})"))


def get_fts_content(db: Session, chunk_id: int) -> str | None:
    row = db.execute(
        sql_text("SELECT content FROM chunk_fts WHERE chunk_id = :chunk_id"),
        {"chunk_id": chunk_id},
    ).fetchone()
    return row[0] if row else None


def _build_match_query(query: str) -> str | None:
    tokens = _TOKEN_RE.findall(query)
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in tokens)


def search_fts(
    db: Session,
    query: str,
    *,
    project_id: int | None = None,
    source_type: str | None = None,
    limit: int = 20,
) -> list[tuple[int, float]]:
    match_query = _build_match_query(query)
    if not match_query:
        return []

    conditions = ["chunk_fts MATCH :match_query"]
    params: dict = {"match_query": match_query, "limit": limit}
    if project_id is not None:
        conditions.append("project_id = :project_id")
        params["project_id"] = project_id
    if source_type is not None:
        conditions.append("source_type = :source_type")
        params["source_type"] = source_type

    sql = (
        "SELECT chunk_id, bm25(chunk_fts) AS score FROM chunk_fts "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY score LIMIT :limit"
    )
    try:
        result = db.execute(sql_text(sql), params)
        return [(row[0], row[1]) for row in result]
    except Exception:
        # A malformed FTS5 query should degrade to "no keyword matches"
        # rather than break the whole search request.
        return []
