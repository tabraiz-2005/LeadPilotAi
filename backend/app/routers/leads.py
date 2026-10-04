"""Lead upload, listing, and integrated AI workflow."""

import io
import re
import pandas as pd
import httpx
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import Lead, OutreachDraft, PortfolioItem, Approval, AgentRun
from app.schemas import LeadOut, LeadUploadResult, AnalyzeRequest
from app.agents.supervisor_agent import execute_run, initial_steps
from uuid import uuid4
from app.services.rag_service import query_portfolio, format_evidence_for_agent

router = APIRouter()


def clean(value):
    return None if pd.isna(value) or value == "" else str(value).strip()


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



@router.delete("/")
def clear_all_leads(db: Session = Depends(get_db)):
    """Delete all leads and their related drafts and decisions."""

    if db.query(AgentRun).filter(AgentRun.status.in_(['pending', 'running'])).first():
        raise HTTPException(409, 'Wait for running analyses before clearing leads.')
    db.query(AgentRun).delete(synchronize_session=False)
    approval_count = db.query(Approval).delete(synchronize_session=False)
    draft_count = db.query(OutreachDraft).delete(synchronize_session=False)
    lead_count = db.query(Lead).delete(synchronize_session=False)

    db.commit()

    return {
        "status": "cleared",
        "deleted_leads": lead_count,
        "deleted_drafts": draft_count,
        "deleted_approvals": approval_count,
    }


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.post("/{lead_id}/analyze", status_code=202)
def analyze_lead(lead_id: int, background: BackgroundTasks,
                 payload: AnalyzeRequest = AnalyzeRequest(), db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    active = db.query(AgentRun).filter(AgentRun.lead_id == lead_id,
                                    AgentRun.status.in_(['pending', 'running'])).first()
    if active:
        return active.as_dict()
    sender = {'name': payload.sender_name.strip() or settings.SENDER_NAME,
              'company': payload.sender_company.strip() or settings.SENDER_COMPANY}
    if not all(sender.values()):
        raise HTTPException(422, 'Enter your real sender name and company in the sidebar before analysis.')
    if not db.query(PortfolioItem).first():
        raise HTTPException(422, 'Upload your portfolio before analyzing leads.')
    if db.query(AgentRun).filter(AgentRun.status.in_(['pending', 'running'])).count() >= 20:
        raise HTTPException(429, 'Analysis queue is full. Please retry shortly.')
    claimed = db.query(Lead).filter(Lead.id == lead_id, Lead.status != 'analyzing').update(
        {'status': 'analyzing'}, synchronize_session=False)
    if not claimed:
        db.rollback()
        raise HTTPException(409, 'This lead is already being analyzed.')
    run = AgentRun(id=uuid4().hex, lead_id=lead_id, status='pending',
                   steps=initial_steps(), sender=sender)
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(execute_run, run.id)
    return run.as_dict()


@router.get("/{lead_id}/runs/{run_id}")
def get_run(lead_id: int, run_id: str, db: Session = Depends(get_db)):
    run = db.get(AgentRun, run_id)
    if not run or run.lead_id != lead_id:
        raise HTTPException(404, 'Agent run not found')
    return run.as_dict()
