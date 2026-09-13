"""Run FastAPI internally when LeadPilot is hosted on Streamlit Cloud."""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _backend_is_running() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8000), timeout=1):
            return True
    except OSError:
        return False


@st.cache_resource(show_spinner="Starting LeadPilot AI services...")
def ensure_backend() -> str:
    """Start FastAPI once and keep it running inside Streamlit's process."""

    if _backend_is_running():
        return "connected"

    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/leadpilot.db")
    os.environ.setdefault("CHROMA_PERSIST_DIR", "/tmp/leadpilot-chroma")
    os.environ.setdefault("ALLOW_ORIGINS", "*")
    os.environ.setdefault("ENABLE_WEB_ENRICHMENT", "true")

    Path("/tmp/leadpilot-chroma").mkdir(parents=True, exist_ok=True)

    import uvicorn
    from app.main import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(60):
        if _backend_is_running():
            return "started"
        time.sleep(0.25)

    raise RuntimeError("LeadPilot backend could not start.")
