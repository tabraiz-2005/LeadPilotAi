"""
FastAPI entrypoint.

This is the file uvicorn actually runs: `uvicorn app.main:app --reload`
It creates the app, turns on CORS (so the Streamlit frontend can call us),
creates database tables on startup, and wires in all the routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.services.groq_client import check_groq_connection

# Import routers - these exist as stub files right now (Step 7 fills in real logic).
from app.routers import portfolio, leads, approvals


# Create all tables on startup if they don't already exist.
# Fine for an MVP/hackathon; a production app would use real migrations instead.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="LeadPilot AI - Backend",
    description="Orchestrates portfolio ingestion, lead processing, RAG retrieval, "
                 "AI agent calls, and the approval workflow.",
    version="0.1.0",
)

# CORS - allows the Streamlit frontend (running on a different port/origin)
# to actually call this API from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire in the routers. Each one owns a URL prefix.
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(leads.router, prefix="/leads", tags=["leads"])
app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])


@app.get("/")
def root():
    """Quick health check - hit this to confirm the server is alive."""
    return {"status": "ok", "service": "LeadPilot backend"}


@app.get("/health/ai")
def ai_health():
    """Safe diagnostic: validates Groq without exposing the API key."""
    return check_groq_connection()
