from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import pytest
from streamlit.testing.v1 import AppTest
from .test_integration import seed, analyze, RESEARCH, FIT, DRAFT, GOOD

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
sys.path.insert(0, str(FRONTEND))

def bridge(response):
    return SimpleNamespace(ok=response.is_success, status_code=response.status_code,
                           text=response.text, content=response.content, json=response.json)

@pytest.mark.parametrize('page', ['Overview','Upload Portfolio','Upload Leads','Lead Dashboard','Lead Detail & Approval'])
def test_pages_render_without_exceptions(client, monkeypatch, page):
    monkeypatch.setenv('BACKEND_URL','http://testserver')
    lead_id = seed(client)
    analyze(client, lead_id)
    with patch('requests.get', side_effect=lambda url, **kwargs: bridge(client.get(url.replace('http://testserver','')))):
        at = AppTest.from_file(str(FRONTEND / 'app.py'))
        at.session_state['page'] = page
        at.session_state['nav_page'] = page
        at.session_state['selected_lead_id'] = lead_id
        at.run(timeout=20)
        assert not at.exception, [e.message for e in at.exception]
        if page == 'Lead Detail & Approval':
            assert any(s.value == 'Agent execution trace' for s in at.subheader)
            assert at.text_area[0].value == DRAFT.email_draft
            assert any(t.value == DRAFT.subject_line for t in at.text_input)


def test_analyze_button_completes_and_renders_trace(client, monkeypatch):
    monkeypatch.setenv('BACKEND_URL','http://testserver')
    lead_id = seed(client)
    with patch('requests.get', side_effect=lambda url, **kwargs: bridge(client.get(url.replace('http://testserver','')))), \
         patch('requests.post', side_effect=lambda url, **kwargs: bridge(client.post(url.replace('http://testserver',''),json=kwargs.get('json')))), \
         patch('app.agents.supervisor_agent.run_research_agent', return_value=RESEARCH), \
         patch('app.agents.supervisor_agent.run_fit_scorer_agent', return_value=FIT), \
         patch('app.agents.supervisor_agent.run_outreach_agent', return_value=DRAFT), \
         patch('app.agents.validation_agent.run_json_agent', return_value=GOOD):
        at = AppTest.from_file(str(FRONTEND / 'app.py'))
        at.session_state['page'] = 'Lead Detail & Approval'
        at.session_state['nav_page'] = 'Lead Detail & Approval'
        at.session_state['selected_lead_id'] = lead_id
        at.session_state['sender_name'] = 'Jordan Rivera'
        at.session_state['sender_company'] = 'Rivera Studio'
        at.run(timeout=20)
        next(b for b in at.button if 'Analyze this lead' in b.label).click().run(timeout=20)
        assert not at.exception, [e.message for e in at.exception]
        assert any(s.value == 'Agent execution trace' for s in at.subheader)
        assert client.get(f'/leads/{lead_id}').json()['status'] == 'analyzed'
