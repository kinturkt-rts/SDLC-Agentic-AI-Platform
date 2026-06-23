"""Amazon Bedrock client for Claude Sonnet inference.

Retries up to 3 times with exponential back-off.
Tests mock `get_bedrock_client` at the router import site.
"""
from __future__ import annotations

import json
import logging
import time
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


class BedrockClient:
    """Thin wrapper around boto3 bedrock-runtime for text inference."""

    def __init__(self) -> None:
        import boto3

        settings = get_settings()
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.bedrock_region or settings.aws_region,
        )
        self._model_id = settings.bedrock_model_id
        self._max_tokens = settings.bedrock_max_tokens

    def invoke_text(self, system_prompt: str, user_message: str) -> str:
        """Invoke Claude Sonnet and return the response text."""
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self._max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
        body = json.dumps(payload)

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                resp = self._client.invoke_model(
                    modelId=self._model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )
                result = json.loads(resp["body"].read())
                text = result["content"][0]["text"]
                duration = time.monotonic() - t0
                logger.info(
                    "bedrock_invoke model=%s attempt=%d duration_ms=%.0f",
                    self._model_id,
                    attempt,
                    duration * 1000,
                )
                return text
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "bedrock_retry attempt=%d error=%s", attempt, exc
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))

        raise RuntimeError(
            f"Bedrock invocation failed after {_MAX_RETRIES} attempts: {last_exc}"
        ) from last_exc


@lru_cache(maxsize=1)
def get_bedrock_client() -> BedrockClient:
    return BedrockClient()
