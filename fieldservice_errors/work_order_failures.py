"""Domain decision for grouping failures from field-service photo work."""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, Field

from .infrai_client import InfraiClient


class WorkOrderPhotoFailure(BaseModel):
    work_order_id: str = Field(min_length=1)
    photo_stage: Literal["capture", "upload", "review"]
    dispatch_status: Literal["unassigned", "dispatched", "on_site", "completed"]
    technician_follow_up: str = Field(min_length=1)
    exception_type: str = Field(min_length=1)
    exception_message: str = Field(min_length=1)
    traceback: str = Field(min_length=1)
    occurrence_id: str = Field(min_length=1)


class CaptureReceipt(BaseModel):
    captured: bool
    grouping_fingerprint: list[str]
    backend_data: dict[str, Any]


def grouping_fingerprint(failure: WorkOrderPhotoFailure) -> list[str]:
    """Keep retries together while separating failures at different photo stages."""
    return [failure.work_order_id, failure.photo_stage, failure.exception_type]


def capture_work_order_failure(
    failure: WorkOrderPhotoFailure, client: InfraiClient
) -> CaptureReceipt:
    fingerprint = grouping_fingerprint(failure)
    stable_id = hashlib.sha256(failure.occurrence_id.encode("utf-8")).hexdigest()
    data = client.capture_exception(
        title=f"Work order {failure.work_order_id} photo {failure.photo_stage} failed",
        message=f"{failure.exception_type}: {failure.exception_message}",
        level="error",
        fingerprint=fingerprint,
        exception=failure.traceback,
        context={
            "work_order_id": failure.work_order_id,
            "photo_stage": failure.photo_stage,
            "dispatch_status": failure.dispatch_status,
            "technician_follow_up": failure.technician_follow_up,
            "occurrence_id": failure.occurrence_id,
        },
        idempotency_key=f"work-order-error-{stable_id}",
    )
    return CaptureReceipt(
        captured=True,
        grouping_fingerprint=fingerprint,
        backend_data=data,
    )
