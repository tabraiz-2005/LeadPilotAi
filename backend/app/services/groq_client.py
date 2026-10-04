"""OpenAI-compatible LLM client (Groq by default, OpenRouter via LLM_BASE_URL)."""
import re
import time
import httpx
from app.config import settings


def _base_url() -> str:
    return settings.LLM_BASE_URL.rstrip("/")


def _headers() -> dict:
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}",
               "Content-Type": "application/json", "User-Agent": "LeadPilotAI/1.0"}
    if "openrouter.ai" in _base_url():
        headers["HTTP-Referer"] = "https://leadpilot-ai.streamlit.app"
        headers["X-Title"] = "LeadPilot AI"
    return headers


def _provider() -> str:
    return "OpenRouter" if "openrouter.ai" in _base_url() else "Groq"


def call_groq(messages, temperature=0.7, model=None, max_tokens=2200) -> str:
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        raise RuntimeError("GROQ_API_KEY is missing. Add your API key and restart.")
    payload = {"model": model or settings.GROQ_MODEL, "messages": messages,
               "temperature": temperature, "max_tokens": max_tokens}
    with httpx.Client(timeout=90.0) as client:
        for attempt in range(6):
            try:
                response = client.post(f"{_base_url()}/chat/completions", headers=_headers(), json=payload)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError("AI provider could not be reached after 3 attempts. Please retry.") from exc
            if response.is_success:
                break
            try:
                message = response.json().get("error", {}).get("message", response.text)
            except Exception:
                message = response.text
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 5:
                retry_header = response.headers.get("retry-after", "")
                match = re.search(r"try again in ([0-9.]+)s", str(message), flags=re.I)
                retry = float(retry_header) if retry_header.replace(".", "", 1).isdigit() else None
                if retry is None and match:
                    retry = float(match.group(1))
                time.sleep(min(max((retry or 8.0) + 1.0, 2.0), 60.0))
                continue
            raise RuntimeError(f"AI provider returned HTTP {response.status_code}: {str(message)[:200]}")
        else:
            raise RuntimeError("AI rate limit remained active after automatic retries.")
    return response.json()["choices"][0]["message"]["content"]


def get_completion(messages, **kwargs) -> str:
    return call_groq(messages, **kwargs)


def check_groq_connection() -> dict:
    base = {"configured": True, "model": settings.GROQ_MODEL}
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY == "your_groq_api_key_here":
        return {**base, "status": "error", "configured": False, "message": "Add your API key and restart."}
    try:
        response = httpx.get(f"{_base_url()}/models", headers=_headers(), timeout=15.0)
        if not response.is_success:
            return {**base, "status": "error", "message": f"{_provider()} rejected the request: {response.text[:300]}"}
        ids = {item.get("id") for item in response.json().get("data", [])}
        if settings.GROQ_MODEL not in ids and _provider() != "OpenRouter":
            return {**base, "status": "error", "message": f"The configured model '{settings.GROQ_MODEL}' is not available."}
        return {**base, "status": "ok", "message": f"{_provider()} key and model are ready."}
    except Exception as exc:
        return {**base, "status": "error", "message": f"Could not reach {_provider()}: {exc}"}
