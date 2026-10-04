import os
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_DIR = tempfile.mkdtemp(prefix='leadpilot-tests-')
os.environ['DATABASE_URL'] = f'sqlite:///{TEST_DIR}/test.db'
os.environ['CHROMA_PERSIST_DIR'] = f'{TEST_DIR}/chroma'
os.environ['ENABLE_WEB_ENRICHMENT'] = 'false'
os.environ['GROQ_API_KEY'] = ''
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as client:
        yield client
