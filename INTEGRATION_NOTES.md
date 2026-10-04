# Integration contract — supervisor update

`POST /leads/{id}/analyze` accepts optional `sender_name` and `sender_company` fields (server settings are fallback). It returns HTTP 202 with a persisted run ID and immediately schedules the supervisor. A second request for the same active lead returns its existing run.

Poll `GET /leads/{id}/runs/{run_id}` for run status, current agent, steps, evidence, validation and final report. Run statuses: pending, running, completed, needs_review, failed. Step statuses: pending, running, completed, failed. An intentionally omitted outreach step is completed with an explanatory output and attempt 0. A validation failure is visible during the rewrite, then the final attempt replaces its stage status; all validation attempts remain available.

`GET /leads/{id}` keeps existing lead/draft fields and adds `subject_line` and `latest_run`. The report includes fit score/reason, qualification decision, source-linked claims, and the final review outcome.

Approvals require a completed validated run and a draft. Editing messages revalidates them before saving; failed edits do not overwrite approved content. Re-analysis clears prior approval and replaces the draft. Nothing is delivered to an email or LinkedIn service.

The new `agent_runs` table is additive. Existing schema remains compatible. Use a single backend worker; see UPDATE_GUIDE.md for storage and hosting constraints.
