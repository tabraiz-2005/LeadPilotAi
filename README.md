# LeadPilot AI

Evidence-grounded lead qualification and outreach with a visible supervisor workflow.

**Research → Fit Scoring → Portfolio Retrieval → Outreach → Validation → Human Review**

- Upload your portfolio and a CSV of prospects.
- Watch each agent's real progress and inspect retrieved evidence.
- Get a personalized email with subject and a shorter LinkedIn follow-up.
- Validate sources, relevance, message length and sender identity; rewrite once if needed.
- Review, edit and approve or reject. No messages are sent automatically.

See **[UPDATE_GUIDE.md](UPDATE_GUIDE.md)** for setup, existing-deployment update instructions, API changes, testing and deployment limitations.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env
# Set GROQ_API_KEY and your real sender identity.
streamlit run frontend/app.py
```

Backend: FastAPI / SQLAlchemy / Chroma. Frontend: Streamlit. AI provider: Groq.
