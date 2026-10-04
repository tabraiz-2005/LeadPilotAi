"""Supervisor coordinates existing agents and persists observable execution."""
from datetime import datetime
from threading import BoundedSemaphore
import logging
from app.database import SessionLocal
from app.models import Lead, AgentRun, PortfolioItem, OutreachDraft, Approval
from app.agents.research_agent import run_research_agent
from app.agents.fit_scorer_agent import run_fit_scorer_agent
from app.agents.outreach_agent import run_outreach_agent
from app.agents.validation_agent import validate_messages, repair_evidence
from app.services.rag_service import query_portfolio

logger = logging.getLogger(__name__)
SLOTS = BoundedSemaphore(2)
STEPS = ['Supervisor Agent', 'Research Agent', 'Fit Scoring Agent',
         'Portfolio Retrieval', 'Outreach Agent', 'Message Validation Agent']


def initial_steps():
    return [{'agent': name, 'status': 'pending', 'output': '', 'attempt': 0} for name in STEPS]


def execute_run(run_id):
    with SLOTS, SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        if not run or run.status != 'pending':
            return
        lead = db.get(Lead, run.lead_id)
        if not lead:
            return

        def step(name, status, output='', attempt=1):
            run.steps = [dict(s, status=status, output=output, attempt=attempt)
                         if s['agent'] == name else dict(s) for s in run.steps]
            if status == 'running':
                run.current_agent = name
            run.updated_at = datetime.utcnow()
            db.commit()

        def finish(status, report):
            run.status, run.report = status, {**(run.report or {}), **report}
            run.current_agent = None
            lead.status = 'analyzed' if status == 'completed' else status
            step('Supervisor Agent', 'completed' if status == 'completed' else 'failed', report['summary'])

        try:
            run.status = 'running'
            step('Supervisor Agent', 'running', f'Coordinating lead: {lead.company_name}')
            row = {k: getattr(lead, k) for k in ['company_name', 'website', 'industry', 'contact_name', 'contact_email']}
            # Prior decisions and drafts must not remain approved during a new run.
            db.query(Approval).filter_by(lead_id=lead.id).delete()
            db.query(OutreachDraft).filter_by(lead_id=lead.id).delete()
            lead.fit_score = lead.confidence = lead.company_summary = lead.fit_explanation = None
            lead.matching_skills = lead.portfolio_evidence = lead.evidence_sources = []
            db.commit()
            step('Research Agent', 'running', 'Reading lead fields and optional public homepage.')
            from app.services.web_research import fetch_public_excerpt
            excerpt = fetch_public_excerpt(lead.website)
            research = run_research_agent(row, excerpt)
            run.report = {'web_excerpt': excerpt}
            lead.company_summary, lead.evidence_sources = research.company_summary, research.evidence_sources
            step('Research Agent', 'completed', research.company_summary)

            step('Fit Scoring Agent', 'running', 'Assessing research against uploaded portfolio capabilities.')
            items = db.query(PortfolioItem).order_by(PortfolioItem.id).all()
            summary = '\n'.join(f'Item {item.id} ({item.title}): {item.content[:2000]}' for item in items)[:12000]
            if not summary:
                raise RuntimeError('Upload a portfolio before analyzing leads.')
            fit = run_fit_scorer_agent(research, summary, summary)
            lead.fit_score, lead.confidence = fit.fit_score, fit.confidence
            lead.fit_explanation, lead.matching_skills = fit.explanation, fit.matching_skills
            step('Fit Scoring Agent', 'completed', f'{fit.fit_score} fit ({fit.confidence:.0%} confidence): {fit.explanation}')

            step('Portfolio Retrieval', 'running', 'Retrieving source excerpts relevant to this lead.')
            matches = query_portfolio(' '.join([lead.company_name, lead.industry or '', research.company_summary,
                                              *research.likely_needs, *fit.matching_skills]), top_k=2)
            valid_items = {str(i.id): i for i in items}
            evidence = []
            for match in matches:
                item_id = str((match.get('metadata') or {}).get('item_id', ''))
                item = valid_items.get(item_id)
                document = ' '.join(str(match.get('document', '')).split())
                # Avoid orphaned vector records after a failed upload/deletion.
                if item and document and document in ' '.join(item.content.split()):
                    evidence.append({'id': f'E{len(evidence)+1}', 'item_id': item_id,
                                     'title': item.title, 'file_name': item.file_name, 'document': document})
            run.evidence = evidence
            lead.portfolio_evidence = [e['document'] for e in evidence]
            step('Portfolio Retrieval', 'completed', f'Retrieved {len(evidence)} source excerpts.')
            if fit.fit_score == 'Low' or not evidence:
                reason = 'Low fit: outreach withheld.' if fit.fit_score == 'Low' else 'No verified portfolio excerpts: outreach withheld.'
                for name in ['Outreach Agent', 'Message Validation Agent']:
                    step(name, 'completed', 'Not required. ' + reason, attempt=0)
                finish('completed', {'qualified': False, 'fit_score': fit.fit_score,
                                    'fit_reason': fit.explanation, 'summary': reason})
                return
            for attempt in (1, 2):
                step('Outreach Agent', 'running', 'Drafting email and LinkedIn follow-up.' if attempt == 1
                     else 'Rewriting once using validation feedback.', attempt)
                outreach = run_outreach_agent(research, fit, evidence, lead=row, sender=run.sender,
                                             correction_feedback=run.validation.get('issues', []))
                outreach = repair_evidence(outreach, evidence)
                step('Outreach Agent', 'completed', outreach.rag_evidence_summary, attempt)
                step('Message Validation Agent', 'running', 'Checking personalization, sources, length, claims, CTA and identity.', attempt)
                validation = validate_messages(outreach, row, research, evidence, run.sender, excerpt)
                previous = run.validation.get('attempts', [])
                run.validation = dict(validation.model_dump(), attempts=previous + [dict(validation.model_dump(), attempt=attempt)])
                step('Message Validation Agent', 'completed' if validation.passed else 'failed',
                     'All validation checks passed.' if validation.passed else '; '.join(validation.issues), attempt)
                if validation.passed:
                    break
            draft = OutreachDraft(lead_id=lead.id, research_notes=research.model_dump_json(),
                                  subject_line=outreach.subject_line, message_body=outreach.email_draft,
                                  linkedin_message=outreach.linkedin_draft,
                                  rag_evidence_summary=outreach.rag_evidence_summary)
            db.add(draft)
            finish('completed' if validation.passed else 'needs_review', {
                'qualified': True, 'fit_score': fit.fit_score, 'fit_reason': fit.explanation,
                'evidence_used': [e.model_dump() for e in outreach.evidence_used],
                'evidence_summary': outreach.rag_evidence_summary,
                'summary': 'Validated drafts ready for human review.' if validation.passed
                           else 'Validation failed after one rewrite. Approval is blocked.',
            })
        except Exception as exc:
            logger.exception('Agent run %s failed', run_id)
            db.rollback()
            run = db.get(AgentRun, run_id)
            lead = db.get(Lead, run.lead_id)
            # Do not expose provider payloads or credentials in persisted/public errors.
            message = str(exc) if isinstance(exc, RuntimeError) else 'Workflow failed. Check server logs and retry.'
            run.error = message[:500]
            failed_agent = run.current_agent or 'Supervisor Agent'
            run.status = 'failed'
            lead.status = 'failed'
            step(failed_agent, 'failed', run.error)
            step('Supervisor Agent', 'failed', 'Workflow stopped; retry after resolving the reported error.')
            run.current_agent = None
            db.commit()
