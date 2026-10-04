from unittest.mock import patch
import pytest
from app.schemas import ResearchOutput, FitScoreOutput, OutreachOutput, ValidationOutput
from app.database import SessionLocal
from app.models import AgentRun, Lead

CONTENT = 'Built SaaS onboarding with FastAPI. Designed accessible forms and product analytics.'
QUOTE = 'Built SaaS onboarding with FastAPI.'
SENDER = {'sender_name': 'Jordan Rivera', 'sender_company': 'Rivera Studio'}
RESEARCH = ResearchOutput(company_summary='Acme AI is a SaaS company.', likely_needs=['onboarding'], evidence_sources=['lead_csv_row.industry'])
FIT = FitScoreOutput(fit_score='High', confidence=.9, explanation='SaaS onboarding matches portfolio experience.', matching_skills=['FastAPI'])
EMAIL = '''Hi Jane,
Acme AI works in SaaS, where getting new customers through onboarding may be a useful area to explore. I would be interested in learning whether this is a current priority for your team before suggesting any changes.
My portfolio includes this example: "Built SaaS onboarding with FastAPI." That experience could be relevant to a focused review of your signup journey and an initial onboarding prototype, depending on what your team needs.
Would you be open to a short conversation about your priorities and whether this approach could help Acme AI?
Best,
Jordan Rivera
Rivera Studio'''
LINKEDIN = '''Hi Jane, I’m Jordan Rivera at Rivera Studio. For Acme AI, could onboarding be a useful area to explore? My portfolio says "Built SaaS onboarding with FastAPI." Would you be open to a short conversation?'''
DRAFT = OutreachOutput(subject_line='An onboarding idea for Acme AI', email_draft=EMAIL,
                       linkedin_draft=LINKEDIN, evidence_used=[{'evidence_id':'E1','quote':QUOTE}],
                       rag_evidence_summary='E1: SaaS onboarding implementation, relevant to Acme AI.')
GOOD = ValidationOutput(passed=True, checks={k:True for k in ['personalization','grounded_claims','honest_sender','service_proposal','call_to_action']})


def seed(client):
    # Actual parsing, database persistence and Chroma retrieval, no mocked RAG.
    result = client.post('/portfolio/upload', files=[('files', ('case.txt', CONTENT.encode(), 'text/plain'))])
    assert result.status_code == 200, result.text
    result = client.post('/leads/upload', files={'file': ('leads.csv', b'company_name,industry,contact_name\nAcme AI,SaaS,Jane\n', 'text/csv')})
    assert result.status_code == 200
    return result.json()['lead_ids'][0]


def analyze(client, lead_id, drafts=None, review=None, fit=FIT):
    with patch('app.agents.supervisor_agent.run_research_agent', return_value=RESEARCH), \
         patch('app.agents.supervisor_agent.run_fit_scorer_agent', return_value=fit), \
         patch('app.agents.supervisor_agent.run_outreach_agent', side_effect=drafts or [DRAFT]) as outreach, \
         patch('app.agents.validation_agent.run_json_agent', return_value=review or GOOD):
        result = client.post(f'/leads/{lead_id}/analyze', json=SENDER)
    assert result.status_code == 202, result.text
    run = client.get(f"/leads/{lead_id}/runs/{result.json()['id']}").json()
    return run, outreach.call_count


def test_full_workflow_real_rag_and_approval(client):
    assert client.get('/').status_code == 200
    lead_id = seed(client)
    run, count = analyze(client, lead_id)
    assert run['status'] == 'completed', run
    assert count == 1
    assert all(s['status'] == 'completed' for s in run['steps'])
    assert run['evidence'][0]['document'] == CONTENT
    assert run['validation']['passed'] is True
    lead = client.get(f'/leads/{lead_id}').json()
    assert lead['subject_line'] == DRAFT.subject_line
    assert lead['email_draft'] == EMAIL
    assert lead['linkedin_draft'] == LINKEDIN
    assert lead['latest_run']['id'] == run['id']
    assert client.post('/approvals/', json={'lead_id':lead_id,'decision':'approve'}).status_code == 200
    assert client.get(f'/leads/{lead_id}').json()['status'] == 'approved'
    assert client.post('/approvals/', json={'lead_id':lead_id,'decision':'edit','email_draft':'Unsupported edit'}).status_code == 422
    assert client.get(f'/leads/{lead_id}').json()['email_draft'] == EMAIL


def test_one_rewrite_and_then_pass(client):
    lead_id = seed(client)
    run, count = analyze(client, lead_id, drafts=[OutreachOutput(email_draft='Hi'), DRAFT])
    assert count == 2
    assert run['status'] == 'completed'
    assert len(run['validation']['attempts']) == 2
    assert run['validation']['attempts'][0]['passed'] is False


def test_second_validation_failure_blocks_approval(client):
    lead_id = seed(client)
    run, count = analyze(client, lead_id, drafts=[DRAFT,DRAFT], review=ValidationOutput(passed=False, issues=['Unsupported company claim']))
    assert count == 2 and run['status'] == 'needs_review'
    assert client.post('/approvals/', json={'lead_id':lead_id,'decision':'approve'}).status_code == 409


def test_low_fit_no_outreach(client):
    lead_id = seed(client)
    run, count = analyze(client, lead_id, fit=FIT.model_copy(update={'fit_score':'Low'}))
    assert run['status'] == 'completed' and run['report']['qualified'] is False
    assert count == 0
    assert client.get(f'/leads/{lead_id}').json()['email_draft'] is None


def test_no_evidence_no_outreach(client):
    lead_id = seed(client)
    with patch('app.agents.supervisor_agent.query_portfolio', return_value=[]):
        run, count = analyze(client, lead_id)
    assert count == 0 and not run['report']['qualified']


def test_provider_failure_persisted(client):
    lead_id = seed(client)
    with patch('app.agents.supervisor_agent.run_research_agent', side_effect=RuntimeError('AI provider returned HTTP 503.')):
        result = client.post(f'/leads/{lead_id}/analyze', json=SENDER)
    run = client.get(f"/leads/{lead_id}/runs/{result.json()['id']}").json()
    assert run['status'] == 'failed'
    assert '503' in run['error']
    assert next(s for s in run['steps'] if s['agent'] == 'Research Agent')['status'] == 'failed'


def test_sender_and_portfolio_required(client):
    result = client.post('/leads/upload', files={'file': ('leads.csv', b'company_name\nAcme AI\n', 'text/csv')})
    lead_id = result.json()['lead_ids'][0]
    assert client.post(f'/leads/{lead_id}/analyze', json={}).status_code == 422
    assert client.post(f'/leads/{lead_id}/analyze', json=SENDER).status_code == 422


def test_duplicate_run_and_delete_protection(client):
    lead_id = seed(client)
    with patch('app.routers.leads.execute_run') as execute:
        first = client.post(f'/leads/{lead_id}/analyze', json=SENDER).json()
        second = client.post(f'/leads/{lead_id}/analyze', json=SENDER).json()
    assert first['id'] == second['id'] and execute.call_count == 1
    assert client.delete('/leads/').status_code == 409
    assert client.post('/approvals/', json={'lead_id':lead_id, 'decision':'reject'}).status_code == 409


def test_restart_recovery(client):
    lead_id = seed(client)
    with patch('app.routers.leads.execute_run'):
        client.post(f'/leads/{lead_id}/analyze', json=SENDER)
    from app.main import recover_interrupted_runs
    recover_interrupted_runs()
    lead = client.get(f'/leads/{lead_id}').json()
    assert lead['status'] == 'failed' and lead['latest_run']['status'] == 'failed'
    assert 'restarted' in lead['latest_run']['error']


def test_regenerate_clears_previous_decision(client):
    lead_id = seed(client)
    analyze(client, lead_id)
    client.post('/approvals/', json={'lead_id':lead_id,'decision':'approve'})
    analyze(client, lead_id)
    assert client.get('/approvals/' + str(lead_id)).status_code == 404
    assert client.get(f'/leads/{lead_id}').json()['status'] == 'analyzed'


def test_valid_edited_messages_revalidated(client):
    lead_id = seed(client)
    analyze(client, lead_id)
    with patch('app.agents.validation_agent.run_json_agent', return_value=GOOD) as review:
        response = client.post('/approvals/', json={'lead_id':lead_id, 'decision':'edit',
                                                  'email_draft': EMAIL.replace('Best,', 'Kind regards,')})
    assert response.status_code == 200, response.text
    assert review.call_count == 1
    assert client.get(f'/leads/{lead_id}').json()['latest_run']['validation']['human_edit_validated']


def test_needs_review_unblocked_by_validated_human_edit(client):
    lead_id = seed(client)
    bad = DRAFT.model_copy(update={'email_draft': EMAIL.replace('"Built SaaS onboarding with FastAPI."', 'onboarding work.')})
    run, count = analyze(client, lead_id, drafts=[bad, bad])
    assert count == 2 and run['status'] == 'needs_review'
    # A bad human edit is still rejected...
    assert client.post('/approvals/', json={'lead_id': lead_id, 'decision': 'edit',
                                            'email_draft': 'Hi'}).status_code == 422
    # ...but a fixed draft passes full validation and is approved.
    with patch('app.agents.validation_agent.run_json_agent', return_value=GOOD):
        response = client.post('/approvals/', json={'lead_id': lead_id, 'decision': 'edit',
                                                    'email_draft': EMAIL, 'linkedin_draft': LINKEDIN})
    assert response.status_code == 200, response.text
    assert client.get(f'/leads/{lead_id}').json()['status'] == 'approved'
