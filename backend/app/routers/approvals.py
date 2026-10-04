"""Human approval, editing, and rejection routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Lead, Approval, OutreachDraft, AgentRun
from app.schemas import OutreachOutput, ResearchOutput
from app.agents.validation_agent import validate_messages
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
    run = db.query(AgentRun).filter_by(lead_id=lead.id).order_by(AgentRun.created_at.desc()).first()
    if run and run.status in ('pending', 'running'):
        raise HTTPException(409, 'Wait for analysis to finish before making a decision.')
    if normalized == 'approved':
        changed = bool(draft) and payload.decision == 'edit' and (
            (payload.email_draft is not None and payload.email_draft != draft.message_body) or
            (payload.linkedin_draft is not None and payload.linkedin_draft != draft.linkedin_message))
        if changed and run and run.status in ('completed', 'needs_review'):
            candidate = OutreachOutput(
                subject_line=draft.subject_line,
                email_draft=payload.email_draft if payload.email_draft is not None else draft.message_body,
                linkedin_draft=payload.linkedin_draft if payload.linkedin_draft is not None else draft.linkedin_message,
                evidence_used=run.report.get('evidence_used', []))
            row = {k: getattr(lead, k) for k in ['company_name', 'website', 'industry', 'contact_name', 'contact_email']}
            try:
                validation = validate_messages(candidate, row, ResearchOutput.model_validate_json(draft.research_notes),
                                               run.evidence, run.sender, run.report.get('web_excerpt', ''))
            except RuntimeError:
                raise HTTPException(503, 'Unable to validate edits right now. No changes were saved.')
            if not validation.passed:
                raise HTTPException(422, 'Edited messages failed validation: ' + '; '.join(validation.issues))
            draft.message_body, draft.linkedin_message = candidate.email_draft, candidate.linkedin_draft
            run.validation = {**validation.model_dump(), 'attempts': (run.validation or {}).get('attempts', []),
                              'human_edit_validated': True}
            # A human fix that passes the full validator unblocks a needs_review run.
            run.status = 'completed'
        elif not draft or not run or run.status != 'completed' or not (run.validation or {}).get('passed'):
            raise HTTPException(409, 'Outreach must pass validation before approval. '
                                     'Edit the drafts so they pass validation, or regenerate analysis.')
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
