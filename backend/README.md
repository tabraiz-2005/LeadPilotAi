# LeadPilot Backend

FastAPI API connecting lead upload, portfolio RAG, Groq agents, SQLite, and approval.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
# Put your own GROQ_API_KEY in .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` to inspect the API.
