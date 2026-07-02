from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    root_path: str
