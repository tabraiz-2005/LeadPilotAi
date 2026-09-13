import os
import tempfile
from unittest.mock import patch

_tmp = tempfile.mkdtemp(prefix="leadpilot-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/leadpilot.db"
os.environ["CHROMA_PERSIST_DIR"] = f"{_tmp}/chroma"
os.environ["ENABLE_WEB_ENRICHMENT"] = "false"

from fastapi.testclient import TestClient
from app.main import app
from app.schemas import ResearchOutput, FitScoreOutput, OutreachOutput

client = TestClient(app)


def test_complete_api_contract():
    assert client.get("/").json()["status"] == "ok"

    with patch("app.routers.portfolio.ingest_portfolio_item"):
        response = client.post(
            "/portfolio/upload",
            files=[("files", ("case.txt", b"Built SaaS onboarding with FastAPI.", "text/plain"))],
        )
    assert response.status_code == 200
    assert response.json()["ingested_count"] == 1

    csv = b"company_name,industry,contact_name\nAcme AI,SaaS,Jane\n"
    response = client.post("/leads/upload", files={"file": ("leads.csv", csv, "text/csv")})
    assert response.status_code == 200
    lead_id = response.json()["lead_ids"][0]

    with patch("app.routers.leads.run_research_agent", return_value=ResearchOutput(
        company_summary="Acme builds SaaS.", likely_needs=["onboarding"], evidence_sources=["CSV"]
    )), patch("app.routers.leads.query_portfolio", return_value=[{
        "document": "Built SaaS onboarding.", "metadata": {"item_id": "1"}, "distance": 0.1
    }]), patch("app.routers.leads.run_fit_scorer_agent", return_value=FitScoreOutput(
        fit_score="High", confidence=.9, explanation="Strong match", matching_skills=["FastAPI"]
    )), patch("app.routers.leads.run_outreach_agent", return_value=OutreachOutput(
        email_draft="Hello Jane", linkedin_draft="Hi Jane", rag_evidence_summary="SaaS case"
    )):
        response = client.post(f"/leads/{lead_id}/analyze", json={})
    assert response.status_code == 200

    lead = client.get(f"/leads/{lead_id}").json()
    assert lead["fit_score"] == "High"
    assert lead["email_draft"] == "Hello Jane"

    response = client.post("/approvals", json={
        "lead_id": lead_id, "decision": "edit", "email_draft": "Edited",
        "linkedin_draft": "Edited LinkedIn", "notes": "Reviewed",
    })
    assert response.status_code == 200
    lead = client.get(f"/leads/{lead_id}").json()
    assert lead["status"] == "approved"
    assert lead["email_draft"] == "Edited"
