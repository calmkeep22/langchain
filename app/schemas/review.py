from pydantic import BaseModel


class ReviewCreateRequest(BaseModel):
    project_id: int
    question: str
    code_top_k: int = 5
    doc_top_k: int = 5
