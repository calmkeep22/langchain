from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ErrorDetail, ErrorResponse, SuccessResponse, new_request_id
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectServiceError, create_project, get_project

router = APIRouter()


def _error_response(exc: ProjectServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(code=exc.code, message=exc.message),
            request_id=new_request_id(),
        ).model_dump(),
    )


@router.post("/projects")
def register_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    try:
        project = create_project(db, payload.name, payload.root_path)
    except ProjectServiceError as exc:
        return _error_response(exc)

    return SuccessResponse(
        data={
            "project_id": project.id,
            "name": project.name,
            "root_path": project.root_path,
        },
        request_id=new_request_id(),
    )


@router.get("/projects/{project_id}")
def read_project(project_id: int, db: Session = Depends(get_db)):
    try:
        project = get_project(db, project_id)
    except ProjectServiceError as exc:
        return _error_response(exc)

    return SuccessResponse(
        data={
            "project_id": project.id,
            "name": project.name,
            "root_path": project.root_path,
            "created_at": project.created_at.isoformat(),
        },
        request_id=new_request_id(),
    )
