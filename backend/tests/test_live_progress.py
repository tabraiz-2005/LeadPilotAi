"""Verify that HTTP analysis returns before work finishes and trace is observable."""
import socket
import threading
import time
from unittest.mock import patch
import httpx
import uvicorn
from app.main import app
from .test_integration import seed, RESEARCH, FIT, DRAFT, GOOD, SENDER


def test_real_http_progress_is_visible_before_completion(client):
    lead_id = seed(client)
    entered, release = threading.Event(), threading.Event()
    def research(*args):
        entered.set()
        assert release.wait(10)
        return RESEARCH
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    with patch('app.agents.supervisor_agent.run_research_agent', side_effect=research) as agent, \
         patch('app.agents.supervisor_agent.run_fit_scorer_agent', return_value=FIT), \
         patch('app.agents.supervisor_agent.run_outreach_agent', return_value=DRAFT), \
         patch('app.agents.validation_agent.run_json_agent', return_value=GOOD):
        thread.start()
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(.01)
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False, timeout=5) as http:
                response = http.post(f'/leads/{lead_id}/analyze', json=SENDER)
                assert response.status_code == 202
                run_id = response.json()['id']
                assert entered.wait(3)
                progress = http.get(f'/leads/{lead_id}/runs/{run_id}').json()
                assert progress['status'] == 'running'
                assert progress['current_agent'] == 'Research Agent'
                duplicate = http.post(f'/leads/{lead_id}/analyze', json=SENDER).json()
                assert duplicate['id'] == run_id
                release.set()
                for _ in range(100):
                    progress = http.get(f'/leads/{lead_id}/runs/{run_id}').json()
                    if progress['status'] not in ('pending','running'): break
                    time.sleep(.02)
                assert progress['status'] == 'completed', progress
                assert agent.call_count == 1
        finally:
            release.set()
            server.should_exit = True
            thread.join(timeout=5)
            sock.close()
