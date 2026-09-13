"""Lead upload, listing, and integrated AI workflow."""

import io
import re
import pandas as pd
import httpx
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import Lead, OutreachDraft, PortfolioItem
from app.schemas import LeadOut, LeadUploadResult, OutreachDraftOut
from app.agents import run_research_agent, run_fit_scorer_agent, run_outreach_agent
from app.services.rag_service import query_portfolio, format_evidence_for_agent

router = APIRouter()


def clean(value):
    return None if pd.isna(value) or value == "" else str(value).strip()


def fetch_public_excerpt(url: str | None) -> str:
    """Optional homepage enrichment. CSV data remains the reliable fallback."""
    if not settings.ENABLE_WEB_ENRICHMENT or not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        response = httpx.get(url, timeout=5.0, follow_redirects=True, headers={"User-Agent": "LeadPilotAI/0.1"})
        response.raise_for_status()
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", response.text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:6000]
    except Exception:
        return ""


@router.post("/upload", response_model=LeadUploadResult)
def upload_leads(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        df = pd.read_csv(io.BytesIO(file.file.read()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}")
    if "company_name" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must include company_name")
    created = []
    for _, row in df.iterrows():
        company_name = clean(row.get("company_name"))
        if not company_name:
            continue
        lead = Lead(company_name=company_name, website=clean(row.get("website")),
                    industry=clean(row.get("industry")), contact_name=clean(row.get("contact_name")),
                    contact_email=clean(row.get("contact_email")), status="pending")
        db.add(lead)
        created.append(lead)
    db.commit()
    for lead in created:
        db.refresh(lead)
    return {"ingested_count": len(created), "lead_ids": [lead.id for lead in created]}


@router.get("/", response_model=list[LeadOut])
def list_leads(db: Session = Depends(get_db)):
    return db.query(Lead).order_by(Lead.created_at.desc()).all()


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("/{lead_id}/analyze", response_model=OutreachDraftOut)
def analyze_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead_row = {"company_name": lead.company_name, "website": lead.website, "industry": lead.industry,
                "contact_name": lead.contact_name, "contact_email": lead.contact_email}
    try:
        research = run_research_agent(lead_row, fetch_public_excerpt(lead.website))
        query = " ".join([lead.company_name, lead.industry or "", research.company_summary, *research.likely_needs])
        matches = query_portfolio(query, top_k=2)
        evidence_text = format_evidence_for_agent(matches)
        portfolio_summary = "\n".join(
            " ".join(item.content.split())[:700]
            for item in db.query(PortfolioItem).limit(2).all()
        )
        fit = run_fit_scorer_agent(research, evidence_text, portfolio_summary)
        outreach = run_outreach_agent(research, fit, evidence_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    lead.status, lead.fit_score, lead.confidence = "analyzed", fit.fit_score, fit.confidence
    lead.company_summary, lead.fit_explanation = research.company_summary, fit.explanation
    lead.matching_skills = fit.matching_skills
    lead.portfolio_evidence = [
        " ".join(str(match.get("document", "")).split())[:520]
        for match in matches
        if match.get("document")
    ]
    lead.evidence_sources = research.evidence_sources
    draft = db.query(OutreachDraft).filter(OutreachDraft.lead_id == lead.id).first()
    if not draft:
        draft = OutreachDraft(lead_id=lead.id)
        db.add(draft)
    draft.research_notes = research.model_dump_json()
    draft.subject_line = f"Idea for {lead.company_name}"
    draft.message_body, draft.linkedin_message = outreach.email_draft, outreach.linkedin_draft
    draft.rag_evidence_summary = outreach.rag_evidence_summary
    db.commit()
    db.refresh(draft)
    return draft
