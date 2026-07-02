from pydantic import BaseModel


class IndexCodeRequest(BaseModel):
    project_id: int
    force_reindex: bool = False
