"""
SQLAlchemy models - these define the actual database tables.

Each class below becomes a real table in leadpilot.db once
Base.metadata.create_all() runs (we'll call that from main.py in Step 5).
"""

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class PortfolioItem(Base):
    """
    A single piece of the company's past work (case study, project, etc.)
    uploaded to build the RAG knowledge base.
    """
    __tablename__ = "portfolio_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)        # extracted text from PDF/docx
    file_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Lead(Base):
    """
    A single lead/prospect uploaded via CSV, tracked through the pipeline:
    pending -> analyzed -> approved/rejected
    """
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

    status = Column(String, default="pending")     # pending | analyzed | approved | rejected
    fit_score = Column(String, nullable=True)       # High | Medium | Low
    confidence = Column(Float, nullable=True)
    company_summary = Column(Text, nullable=True)
    fit_explanation = Column(Text, nullable=True)
    matching_skills = Column(JSON, default=list)
    portfolio_evidence = Column(JSON, default=list)
    evidence_sources = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)

    # One lead can have one outreach draft and one approval decision
    outreach_draft = relationship("OutreachDraft", back_populates="lead", uselist=False)
    approval = relationship("Approval", back_populates="lead", uselist=False)

    @property
    def email_draft(self):
        return self.outreach_draft.message_body if self.outreach_draft else None

    @property
    def linkedin_draft(self):
        return self.outreach_draft.linkedin_message if self.outreach_draft else None


class OutreachDraft(Base):
    """
    The AI-generated outreach message for a lead, produced by the outreach agent
    after research + fit scoring.
    """
    __tablename__ = "outreach_drafts"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)

    research_notes = Column(Text, nullable=True)    # output of research agent
    subject_line = Column(String, nullable=True)
    message_body = Column(Text, nullable=True)
    linkedin_message = Column(Text, nullable=True)
    rag_evidence_summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="outreach_draft")


class Approval(Base):
    """
    Human decision on whether to send the drafted outreach.
    """
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)

    decision = Column(String, nullable=False)       # "approved" | "rejected"
    reviewer_notes = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="approval")
