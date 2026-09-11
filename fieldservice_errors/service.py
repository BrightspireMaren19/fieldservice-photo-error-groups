"""Application entry point for field-service error capture."""

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .work_order_failures import (
    CaptureReceipt,
    WorkOrderPhotoFailure,
    capture_work_order_failure,
)

service = FastAPI(title="Field-service photo error capture")


@service.post("/work-orders/photo-errors", response_model=CaptureReceipt)
def report_photo_error(failure: WorkOrderPhotoFailure) -> CaptureReceipt:
    try:
        return capture_work_order_failure(failure, InfraiClient())
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
