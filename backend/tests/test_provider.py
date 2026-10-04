from unittest.mock import patch
import httpx
import pytest
from app.services.groq_client import call_groq
from app.agents._utils import run_json_agent
from app.schemas import ResearchOutput

@pytest.mark.parametrize('status',[429,500,502,503,504])
def test_transient_provider_errors_retry(status):
    good = httpx.Response(200, json={'choices':[{'message':{'content':'{}'}}]})
    bad = httpx.Response(status, json={'error':{'message':'busy'}})
    with patch('app.services.groq_client.settings.GROQ_API_KEY','test'), \
         patch('httpx.Client') as client,  \
         patch('app.services.groq_client.time.sleep'):
        post = client.return_value.__enter__.return_value.post
        post.side_effect = [bad, good]
        assert call_groq([]) == '{}'
    assert post.call_count == 2


def test_invalid_json_never_silently_succeeds():
    with patch('app.agents._utils.get_completion', return_value='invalid') as completion:
        with pytest.raises(RuntimeError):
            run_json_agent('s','u',ResearchOutput,ResearchOutput())
    assert completion.call_count == 2


def test_network_failure_retries_bounded():
    with patch('app.services.groq_client.settings.GROQ_API_KEY','test'), \
         patch('httpx.Client') as client,  \
         patch('app.services.groq_client.time.sleep'):
        post = client.return_value.__enter__.return_value.post
        post.side_effect = httpx.ConnectError('unavailable')
        with pytest.raises(RuntimeError, match='3 attempts'):
            call_groq([])
    assert post.call_count == 3
