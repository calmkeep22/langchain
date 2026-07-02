from pydantic import BaseModel


class IndexCodeRequest(BaseModel):
    project_id: int
    force_reindex: bool = False


class IndexDocsRequest(BaseModel):
    doc_name: str
    source_type: str = "official_doc"
    path: str | None = None
    url: str | None = None
    max_depth: int = 2
    force_reindex: bool = False
