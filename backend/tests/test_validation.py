from unittest.mock import patch
import pytest
from app.agents.validation_agent import validate_messages
from app.schemas import OutreachOutput, ResearchOutput, EvidenceClaim
from .test_integration import DRAFT, GOOD, RESEARCH, CONTENT

@pytest.mark.parametrize('change', [
    {'email_draft':'Hi'},
    {'linkedin_draft':'x'*601},
    {'subject_line':''},
    {'email_draft': DRAFT.email_draft.replace('Jordan Rivera','Fake Person')},
    {'email_draft': DRAFT.email_draft.replace('Acme AI','Some company')},
    {'evidence_used':[EvidenceClaim(evidence_id='E999', quote='Never appears in any portfolio file.')]},
    {'evidence_used':[EvidenceClaim(evidence_id='E1', quote='Increased revenue by 500%.')]},
    {'email_draft': DRAFT.email_draft.replace('may be','is guaranteed to be')},
])
def test_invalid_drafts_rejected_without_semantic_call(change):
    with patch('app.agents.validation_agent.run_json_agent') as semantic:
        result = validate_messages(DRAFT.model_copy(update=change), {'company_name':'Acme AI'}, RESEARCH,
                                   [{'id':'E1','document':CONTENT}], {'name':'Jordan Rivera','company':'Rivera Studio'})
    assert not result.passed and result.issues
    semantic.assert_not_called()


def test_semantic_review_cannot_pass_with_missing_checks():
    from app.schemas import ValidationOutput
    with patch('app.agents.validation_agent.run_json_agent', return_value=ValidationOutput(passed=True)):
        result = validate_messages(DRAFT, {'company_name':'Acme AI'}, RESEARCH,
                                   [{'id':'E1','document':CONTENT}], {'name':'Jordan Rivera','company':'Rivera Studio'})
    assert not result.passed


def _run(draft, review=None):
    from .test_integration import GOOD as _GOOD
    with patch('app.agents.validation_agent.run_json_agent', return_value=review or _GOOD) as semantic:
        result = validate_messages(draft, {'company_name':'Acme AI'}, RESEARCH,
                                   [{'id':'E1','document':CONTENT}], {'name':'Jordan Rivera','company':'Rivera Studio'})
    return result, semantic


def test_wrong_evidence_id_is_repaired():
    result, _ = _run(DRAFT.model_copy(update={'evidence_used':[EvidenceClaim(evidence_id='E2', quote='Built SaaS onboarding with FastAPI.')]}))
    assert result.passed, result.issues


def test_curly_quotes_and_missing_period_still_match():
    linkedin = DRAFT.linkedin_draft.replace('"Built SaaS onboarding with FastAPI."', '\u201cBuilt SaaS onboarding with FastAPI\u201d')
    draft = DRAFT.model_copy(update={'linkedin_draft': linkedin,
                                     'evidence_used':[EvidenceClaim(evidence_id='E1', quote='\u201cBuilt SaaS onboarding with FastAPI\u201d')]})
    result, _ = _run(draft)
    assert result.passed, result.issues


def test_linkedin_may_reference_key_words_of_quote():
    linkedin = DRAFT.linkedin_draft.replace('My portfolio says "Built SaaS onboarding with FastAPI."',
                                            'I have built SaaS onboarding flows with FastAPI before.')
    result, _ = _run(DRAFT.model_copy(update={'linkedin_draft': linkedin}))
    assert result.passed, result.issues


def test_quote_missing_from_email_gives_actionable_issue():
    email = DRAFT.email_draft.replace('"Built SaaS onboarding with FastAPI."', 'onboarding work.')
    result, semantic = _run(DRAFT.model_copy(update={'email_draft': email}))
    assert not result.passed and any('inside the email body' in i for i in result.issues)
    semantic.assert_not_called()


def test_quote_not_in_source_is_still_rejected():
    email = DRAFT.email_draft.replace('Built SaaS onboarding with FastAPI.', 'Tripled SaaS revenue with FastAPI.')
    draft = DRAFT.model_copy(update={'email_draft': email,
                                     'evidence_used':[EvidenceClaim(evidence_id='E1', quote='Tripled SaaS revenue with FastAPI.')]})
    result, semantic = _run(draft)
    assert not result.passed and any('not an exact excerpt' in i for i in result.issues)
    semantic.assert_not_called()


def test_quote_candidates_are_exact_substrings():
    from app.agents.validation_agent import quote_candidates
    for c in quote_candidates([{'id':'E1','document':CONTENT}]):
        assert c['quote'] in CONTENT
