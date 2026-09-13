# LeadPilot AI — Integrated Team Build

This project combines the submitted ZIPs into one application:

- `backend/`: FastAPI, SQLite, RAG, agents, and approvals
- `frontend/`: Streamlit user interface
- `docker-compose.yml`: starts both services together

## Fastest start (Docker)

1. Copy `backend/.env.example` to `backend/.env`.
2. Add your own `GROQ_API_KEY` to `backend/.env`.
3. From this folder run `docker compose up --build`.
4. Open `http://localhost:8501`.
5. API documentation is at `http://localhost:8000/docs`.

## Local start without Docker

Use two terminal windows.

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Required user flow

1. Upload at least one PDF, DOCX, or TXT portfolio file.
2. Upload a CSV containing `company_name`; `website`, `industry`, `contact_name`, and `contact_email` are optional.
3. Open Lead Dashboard and choose a lead.
4. Select Analyze. LeadPilot runs Research → RAG → Fit → Outreach.
5. Review/edit the email and LinkedIn draft, then approve or reject it.

CSV data is always the base source. Homepage enrichment is optional and falls back to CSV-only. Nothing is sent automatically.

## Security

Never commit or share `backend/.env`. An uploaded ZIP contained an API-key file;
it is excluded from this package. Create a new key if that key was shared elsewhere.
