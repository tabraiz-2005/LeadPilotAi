"""
Pydantic schemas - these define the shape of data going in and out of the API.

Naming convention used here:
  <Thing>Create  -> what the client sends to create something
  <Thing>Out     -> what the API sends back
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


# ---------- Portfolio ----------

class PortfolioItemOut(BaseModel):
    id: int
    title: str
    file_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True   # lets this read directly from a SQLAlchemy model


class PortfolioUploadResult(BaseModel):
    ingested_count: int
    items: list[PortfolioItemOut]


class LeadUploadResult(BaseModel):
    ingested_count: int
    lead_ids: list[int]


# ---------- Leads ----------

class LeadCreate(BaseModel):
    """What one row of the uploaded CSV looks like."""
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


class LeadOut(BaseModel):
    id: int
    company_name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    status: str
    fit_score: Optional[Literal["High", "Medium", "Low"]] = None
    confidence: Optional[float] = None
    company_summary: Optional[str] = None
    fit_explanation: Optional[str] = None
    matching_skills: list[str] = []
    portfolio_evidence: list[str] = []
    evidence_sources: list[str] = []
    email_draft: Optional[str] = None
    linkedin_draft: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Agent outputs (used internally when chaining research -> fit_scorer -> outreach) ----------

class ResearchOutput(BaseModel):
    company_summary: str = ""
    likely_needs: list[str] = []
    evidence_sources: list[str] = []


class FitScoreOutput(BaseModel):
    fit_score: Literal["High", "Medium", "Low"]
    confidence: float
    explanation: str = ""
    matching_skills: list[str] = []


class OutreachOutput(BaseModel):
    email_draft: str = ""
    linkedin_draft: str = ""
    rag_evidence_summary: str = ""


class OutreachDraftOut(BaseModel):
    id: int
    lead_id: int
    research_notes: Optional[str] = None
    subject_line: Optional[str] = None
    message_body: Optional[str] = None
    linkedin_message: Optional[str] = None
    rag_evidence_summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Approvals ----------

class ApprovalCreate(BaseModel):
    lead_id: int
    decision: str              # "approved" or "rejected"
    reviewer_notes: Optional[str] = None
    notes: Optional[str] = None
    email_draft: Optional[str] = None
    linkedin_draft: Optional[str] = None


class ApprovalOut(BaseModel):
    id: int
    lead_id: int
    decision: str
    reviewer_notes: Optional[str] = None
    decided_at: datetime

    class Config:
        from_attributes = True
