from pathlib import Path

from sqlalchemy.orm import Session

from app.core.errors import ServiceError
from app.models.project import Project


def create_project(db: Session, name: str, root_path: str) -> Project:
    path = Path(root_path)
    if not path.is_dir():
        raise ServiceError("INVALID_PROJECT_PATH", "Project path is invalid.", 400)

    if db.query(Project).filter(Project.name == name).first():
        raise ServiceError("PROJECT_ALREADY_EXISTS", "Project already exists.", 409)

    project = Project(name=name, root_path=root_path)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ServiceError("PROJECT_NOT_FOUND", "Project not found.", 404)
    return project
