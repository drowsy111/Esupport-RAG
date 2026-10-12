from fastapi import APIRouter, Depends

from app.api.dependencies import current_principal, get_resources, get_session
from app.repositories.job_repository import get_job
from app.services.document_service import retry_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def detail(job_id: str, session=Depends(get_session), principal=Depends(current_principal)):
    job = get_job(session, principal, job_id)
    return {"id": job.id, "status": job.status, "stage": job.stage,
            "attempts": job.attempts, "error_code": job.error_code}


@router.post("/{job_id}/retry", status_code=202)
def retry(
    job_id: str, session=Depends(get_session),
    principal=Depends(current_principal), resources=Depends(get_resources),
):
    return retry_job(session, resources, principal, get_job(session, principal, job_id))

