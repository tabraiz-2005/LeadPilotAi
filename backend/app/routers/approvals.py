"""Human approval, editing, and rejection routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Lead, Approval, OutreachDraft
from app.schemas import ApprovalCreate, ApprovalOut

router = APIRouter()


@router.post("/", response_model=ApprovalOut)
def create_approval(payload: ApprovalCreate, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if payload.decision not in ("approve", "approved", "edit", "reject", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be approve, edit, or reject")
    normalized = {
        "approve": "approved", "approved": "approved", "edit": "approved",
        "reject": "rejected", "rejected": "rejected",
    }[payload.decision]
    draft = db.query(OutreachDraft).filter(OutreachDraft.lead_id == payload.lead_id).first()
    if draft and payload.decision == "edit":
        if payload.email_draft is not None:
            draft.message_body = payload.email_draft
        if payload.linkedin_draft is not None:
            draft.linkedin_message = payload.linkedin_draft
    approval = db.query(Approval).filter(Approval.lead_id == payload.lead_id).first()
    if not approval:
        approval = Approval(lead_id=payload.lead_id, decision=normalized)
        db.add(approval)
    approval.decision = normalized
    approval.reviewer_notes = payload.reviewer_notes or payload.notes
    lead.status = normalized
    db.commit()
    db.refresh(approval)
    return approval


@router.get("/{lead_id}", response_model=ApprovalOut)
def get_approval(lead_id: int, db: Session = Depends(get_db)):
    approval = db.query(Approval).filter(Approval.lead_id == lead_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="No approval decision found for this lead")
    return approval
