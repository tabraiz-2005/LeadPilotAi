"""
Shared helper for agents that must return strict JSON validated against a
Pydantic schema.

Flow for every agent call:
    1. Call the model with the agent's normal prompt.
    2. Try to parse + validate the response against `schema_cls`.
    3. If that fails (bad JSON or failed validation), retry once with an
       extra, stricter instruction appended to the conversation.
    4. If the retry also fails, return the caller-supplied `fallback`
       (already a valid instance of `schema_cls`) instead of raising.

This keeps every agent's own module focused on its prompt/business logic
rather than on JSON/retry plumbing.
"""

import json
import logging
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.services.groq_client import get_completion

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_STRICT_RETRY_INSTRUCTION = (
    "Your previous response could not be parsed as valid JSON matching the "
    "required schema. Respond again with ONLY a single valid JSON object: "
    "no markdown, no code fences, no commentary, and no text before or "
    "after the JSON object."
)


def _extract_json_object(text: str) -> str:
    """Best-effort extraction of a top-level JSON object from model output."""
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


def _parse_and_validate(text: str, schema_cls: Type[T]) -> T:
    raw = _extract_json_object(text)
    data = json.loads(raw)
    return schema_cls.model_validate(data)


def run_json_agent(
    system_prompt: str,
    user_prompt: str,
    schema_cls: Type[T],
    fallback: T,
    model: str | None = None,
    temperature: float = 0.3,
) -> T:
    """
    Call the LLM and return a validated `schema_cls` instance.

    Retries once with a stricter prompt on JSON/validation failure (or on
    any transport error from the model call), then returns `fallback`.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    call_kwargs = {"temperature": temperature}
    if model:
        call_kwargs["model"] = model

    try:
        raw_response = get_completion(messages, **call_kwargs)
        return _parse_and_validate(raw_response, schema_cls)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("%s: invalid JSON/schema on first attempt: %s", schema_cls.__name__, exc)
    except Exception as exc:
        logger.exception("%s: Groq request failed: %s", schema_cls.__name__, exc)
        raise RuntimeError(str(exc)) from exc

    retry_messages = messages + [{"role": "user", "content": _STRICT_RETRY_INSTRUCTION}]

    try:
        raw_response = get_completion(retry_messages, **call_kwargs)
        return _parse_and_validate(raw_response, schema_cls)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("%s: invalid JSON/schema on retry: %s", schema_cls.__name__, exc)
    except Exception as exc:
        logger.exception("%s: Groq retry failed: %s", schema_cls.__name__, exc)
        raise RuntimeError(str(exc)) from exc

    logger.error("%s: falling back to schema-valid default output.", schema_cls.__name__)
    return fallback
