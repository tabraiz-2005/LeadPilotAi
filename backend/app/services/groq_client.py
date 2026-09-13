"""
Groq API client.

A single, reusable function that sends messages to Groq's chat completions
endpoint and returns the model's text reply. The AI Agent Lead's agent modules
(research_agent.py, fit_scorer_agent.py, outreach_agent.py) will call this
function - so its signature matters to more than just you.
"""

import re
import time
import httpx

from app.config import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def call_groq(
    messages: list[dict],
    temperature: float = 0.7,
    model: str | None = None,
    max_tokens: int = 700,
) -> str:
    """
    Send a list of chat messages to Groq and return the assistant's reply text.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": "..."}
        temperature: creativity setting, 0 = deterministic, 1 = more varied

    Returns:
        The model's reply as a plain string.

    Raises:
        httpx.HTTPStatusError if Groq returns an error (bad key, rate limit, etc.)
    """
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add a real gsk_... key to backend/.env "
            "and restart the backend."
        )

    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    with httpx.Client(timeout=45.0) as client:
        for attempt in range(3):
            response = client.post(GROQ_API_URL, headers=headers, json=payload)
            if response.is_success:
                break

            try:
                message = response.json().get("error", {}).get("message", response.text)
            except Exception:
                message = response.text

            if response.status_code == 429 and attempt < 2:
                retry_header = response.headers.get("retry-after", "")
                match = re.search(r"try again in ([0-9.]+)s", message, flags=re.I)
                retry_seconds = float(retry_header) if retry_header.replace(".", "", 1).isdigit() else None
                if retry_seconds is None and match:
                    retry_seconds = float(match.group(1))
                time.sleep(min(max((retry_seconds or 8.0) + 1.0, 2.0), 20.0))
                continue

            raise RuntimeError(f"Groq API error {response.status_code}: {message[:500]}")
        else:
            raise RuntimeError("Groq rate limit remained active after automatic retries.")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def get_completion(messages: list[dict], **kwargs) -> str:
    """Compatibility interface used by the independently-built Agent module."""
    return call_groq(messages, **kwargs)


def check_groq_connection() -> dict:
    """Validate the configured key and confirm the selected model exists."""
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        return {
            "status": "error",
            "configured": False,
            "model": settings.GROQ_MODEL,
            "message": "Add a real GROQ_API_KEY to backend/.env and restart the backend.",
        }

    try:
        response = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            timeout=15.0,
        )
        if not response.is_success:
            try:
                message = response.json().get("error", {}).get("message", response.text)
            except Exception:
                message = response.text
            return {
                "status": "error",
                "configured": True,
                "model": settings.GROQ_MODEL,
                "message": f"Groq rejected the key: {message[:300]}",
            }

        model_ids = {item.get("id") for item in response.json().get("data", [])}
        if settings.GROQ_MODEL not in model_ids:
            return {
                "status": "error",
                "configured": True,
                "model": settings.GROQ_MODEL,
                "message": f"The configured model '{settings.GROQ_MODEL}' is not available.",
            }
        return {
            "status": "ok",
            "configured": True,
            "model": settings.GROQ_MODEL,
            "message": "Groq key and model are ready.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "configured": True,
            "model": settings.GROQ_MODEL,
            "message": f"Could not reach Groq: {exc}",
        }
