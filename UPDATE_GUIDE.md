# LeadPilot AI — Supervisor update

## What changed

The supervisor now runs Research → Fit Scoring → Portfolio Retrieval → Outreach → Message Validation, saving real progress after each stage. It reuses the original research/scoring modules and portfolio retrieval service. Scoring uses a bounded overview of uploaded portfolio capabilities; retrieval then selects excerpts for outreach. High and Medium fits with evidence receive drafts. Low fits or missing evidence produce an explicit report without outreach.

Both drafts reference the same 1–2 retrieved excerpts. The email includes a generated subject, greeting, possible company problem, service proposal, evidence and CTA. LinkedIn uses a shorter follow-up format (not the short connection-request note format). Both use your supplied sender identity.

Validation checks email length (80–180 words), LinkedIn length (30–80 words and at most 600 characters), source IDs, exact source quotes, sender identity, placeholders, CTA and exaggerated language. A separate model review checks meaningful personalization, factual support and proposed services. Failed validation triggers exactly one outreach rewrite. A second failure blocks approval. Model review reduces unsupported claims but does not guarantee factual correctness; human review remains required.

The trace panel shows pending/running/completed/failed states, agent summaries, retrieved excerpts and their filenames, score/reason, checks and rewrite history. Progress and results survive browser refreshes. Interrupted runs are marked failed after a backend restart so they can be retried.

## Run locally

Use Python 3.11 or 3.12. From this project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp backend/.env.example backend/.env
```

Put your real `GROQ_API_KEY` in `backend/.env`. Keep your existing working `GROQ_MODEL`, or use the example value if available to your account. Enter `SENDER_NAME` and `SENDER_COMPANY` there, or fill in **Outreach sender** in the sidebar. Your company may be your real professional/freelance identity.

```bash
streamlit run frontend/app.py
```

The embedded backend starts automatically. Open the local address Streamlit prints. Upload your portfolio first, then a CSV with `company_name` and optional `website,industry,contact_name,contact_email`. Open a lead to watch its trace and review the drafts. Nothing is sent automatically.

## Update the already-deployed GitHub project

1. Back up your deployment database and portfolio store if they contain data you need.
2. Copy the updated source files into your existing repository at the same relative paths. `CHANGED_FILES.txt` lists the changed/new files. Keep the repository's `.git` folder, existing secrets and deployment settings.
3. Keep your working API key in the hosting provider's secret settings. Set sender name/company there or use the sidebar. Never commit `.env` or `.streamlit/secrets.toml`.
4. Commit and push to your existing deployment branch when ready. This task has not pushed or deployed anything.
5. Confirm the host's build succeeds, then upload a sample lead and watch the full trace. Approve only after reviewing the evidence and validation result.

Existing leads and drafts use their original tables. Startup creates the new `agent_runs` table automatically; no destructive migration is needed. Old drafts without validation history must be regenerated before approval. This ZIP intentionally excludes databases, vector stores, uploaded client files, `.env`, Git history, caches and macOS metadata; updating source files must not erase your deployed data.

### Hosting notes

- Existing Streamlit entry point remains `frontend/app.py`; requirements are also present under `frontend/` for that host. Configure secrets at the root of Streamlit secrets TOML, using the variable names above.
- Docker/Render entry points remain unchanged. The default Render `/tmp` storage is ephemeral; restarts/redeployments can lose leads and portfolios unless you use persistent storage for both SQLite and Chroma.
- Use **one backend worker**. This is an in-process background supervisor, capped at two simultaneous analyses, not a distributed task queue. Multi-worker/multi-instance deployments need a shared durable queue and worker ownership before scaling.
- The existing application has no user authentication or tenant isolation. Keep it in a trusted demo setting; add access control before exposing real client data in a multi-user public deployment.
- `POST /leads/{id}/analyze` now returns **202 and a run record**, not a finished draft. Poll `GET /leads/{id}/runs/{run_id}`. Updated frontend handles this. `GET /leads/{id}` includes subject, both drafts and latest run.
- Transient 429/500/502/503/504 and connection errors receive bounded retries. Persistent provider outages still surface as failed runs; they cannot be eliminated by application code.

## Validation performed

```bash
python -m pytest backend/tests -q
python -m compileall -q backend/app frontend
pip check
```

Automated tests cover actual TXT portfolio ingestion and Chroma retrieval, database persistence, success, one rewrite, repeated rejection, absent evidence, low fit, required sender, provider failure, duplicate protection, restart recovery, approval/revalidation, all five frontend pages, the Analyze button, and a real HTTP test showing progress while an agent is still running. AI responses are mocked in tests so results are deterministic and no API credits are consumed.

The original SQLite database was copied to a temporary location and the additive table creation was verified to preserve the lead row count. No original data was changed.

Live Groq output, Docker image execution and the hosted deployment are not verified here. Run the existing AI health check with your configured credentials and perform a sample lead run after deployment.
