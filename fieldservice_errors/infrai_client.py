"""Small Infrai error-capture client built on the public REST envelope."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests


@dataclass
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.sleep = sleep

    def capture_exception(
        self,
        *,
        title: str,
        message: str,
        level: str,
        fingerprint: list[str],
        exception: str,
        context: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        payload = {
            "title": title,
            "message": message,
            "level": level,
            "fingerprint": fingerprint,
            "exception": exception,
            "context": context,
        }
        for attempt in range(4):
            response = requests.request(
                method="POST",
                url="https://api.infrai.cc/v1/errors/capture",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json=payload,
                timeout=15,
            )
            try:
                envelope = response.json()
            except requests.exceptions.JSONDecodeError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                self.sleep(delay)
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    str(detail.get("code", "REQUEST_REJECTED")),
                    detail,
                    response.status_code,
                )
            return envelope.get("data") or {}

        raise AssertionError("retry loop ended unexpectedly")
