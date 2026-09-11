from typing import Any

from fieldservice_errors.work_order_failures import (
    WorkOrderPhotoFailure,
    capture_work_order_failure,
)


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def capture_exception(self, **payload: Any) -> dict[str, Any]:
        self.calls.append(payload)
        return {"event_id": "evt_demo"}


def test_photo_retries_group_by_work_order_stage_and_exception() -> None:
    client = RecordingClient()
    first = WorkOrderPhotoFailure(
        work_order_id="WO-1842",
        photo_stage="upload",
        dispatch_status="on_site",
        technician_follow_up="Retry after switching to site Wi-Fi",
        exception_type="ConnectionError",
        exception_message="photo upload interrupted",
        traceback="ConnectionError: photo upload interrupted",
        occurrence_id="mobile-attempt-41",
    )
    second = first.model_copy(update={"occurrence_id": "mobile-attempt-42"})

    first_receipt = capture_work_order_failure(first, client)  # type: ignore[arg-type]
    second_receipt = capture_work_order_failure(second, client)  # type: ignore[arg-type]

    expected = ["WO-1842", "upload", "ConnectionError"]
    assert first_receipt.grouping_fingerprint == expected
    assert second_receipt.grouping_fingerprint == expected
    assert client.calls[0]["context"]["dispatch_status"] == "on_site"
    assert client.calls[0]["context"]["technician_follow_up"].startswith("Retry")
    assert client.calls[0]["idempotency_key"] != client.calls[1]["idempotency_key"]
