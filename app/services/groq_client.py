"""Groq LLM backend exposed through a Bedrock-compatible interface.

This adapter lets the existing Bedrock call sites switch to Groq without
changing how they build messages or parse responses. It mimics the subset of
the Amazon Bedrock ``bedrock-runtime`` ``converse`` API that this project uses:

    response = client.converse(
        modelId=...,
        messages=[{"role": "user", "content": [{"text": "..."}]}],
        system=[{"text": "..."}],            # optional
        inferenceConfig={"maxTokens": 1500, "temperature": 0.2},
    )
    text = response["output"]["message"]["content"][0]["text"]
    stop = response["stopReason"]

Bedrock is intentionally left in place; callers prefer this client only when a
``GROQ_API_KEY`` is configured and otherwise fall back to Bedrock.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    from groq import Groq
except ImportError:  # pragma: no cover - groq is a declared dependency
    Groq = None


# Maps Groq finish_reason values to Bedrock stopReason values so downstream
# code that inspects stopReason keeps working unchanged.
_STOP_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "content_filtered",
}


class GroqConverseClient:
    """Thin wrapper around the Groq SDK that speaks the Bedrock converse shape."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.groq_model
        self._client = None

        if Groq is None:
            logger.warning("groq package not installed; Groq backend unavailable.")
            return
        if not settings.groq_api_key:
            logger.info("GROQ_API_KEY not set; Groq backend unavailable.")
            return

        try:
            self._client = Groq(api_key=settings.groq_api_key)
            logger.info("Groq client initialized: model=%s", self.model)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Groq client init failed: %s", exc)
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    @staticmethod
    def _to_groq_messages(
        messages: list[dict[str, Any]],
        system: list[dict[str, Any]] | None,
    ) -> list[dict[str, str]]:
        """Convert Bedrock-style messages to Groq/OpenAI chat messages."""
        groq_messages: list[dict[str, str]] = []

        if system:
            system_text = "\n".join(
                block["text"] for block in system if isinstance(block, dict) and "text" in block
            )
            if system_text:
                groq_messages.append({"role": "system", "content": system_text})

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", [])
            if isinstance(content, list):
                text = "\n".join(
                    block["text"] for block in content if isinstance(block, dict) and "text" in block
                )
            else:
                text = str(content)
            groq_messages.append({"role": role, "content": text})

        return groq_messages

    def converse(
        self,
        *,
        modelId: str | None = None,
        messages: list[dict[str, Any]],
        system: list[dict[str, Any]] | None = None,
        inferenceConfig: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Bedrock-compatible converse call backed by Groq.

        Note: ``modelId`` (a Bedrock model id) is ignored in favor of the
        configured Groq model. The argument is accepted so existing call sites
        need no changes.
        """
        if self._client is None:
            raise RuntimeError("Groq client is not available.")

        inference = inferenceConfig or {}
        groq_messages = self._to_groq_messages(messages, system)

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=groq_messages,
            max_tokens=inference.get("maxTokens", 1024),
            temperature=inference.get("temperature", 0.2),
        )

        choice = completion.choices[0]
        text = choice.message.content or ""
        stop_reason = _STOP_REASON_MAP.get(choice.finish_reason, "end_turn")

        return {
            "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
            "stopReason": stop_reason,
        }
