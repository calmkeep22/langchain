from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.errors import ServiceError, service_error_response
from app.db.session import get_db
from app.schemas.common import SuccessResponse, current_request_id
from app.schemas.project import ProjectCreate
from app.services.project_service import create_project, get_project

router = APIRouter()


@router.post("/projects")
def register_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    try:
        project = create_project(db, payload.name, payload.root_path)
    except ServiceError as exc:
        return service_error_response(exc)

    return SuccessResponse(
        data={
            "project_id": project.id,
            "name": project.name,
            "root_path": project.root_path,
        },
        request_id=current_request_id(),
    )


@router.get("/projects/{project_id}")
def read_project(project_id: int, db: Session = Depends(get_db)):
    try:
        project = get_project(db, project_id)
    except ServiceError as exc:
        return service_error_response(exc)

    return SuccessResponse(
        data={
            "project_id": project.id,
            "name": project.name,
            "root_path": project.root_path,
            "created_at": project.created_at.isoformat(),
        },
        request_id=current_request_id(),
    )
