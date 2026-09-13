# Integration Notes

| Area | Submission mismatch | Integrated decision |
|---|---|---|
| Portfolio upload | Frontend sent multiple `files`; backend accepted one `file` | Accept multiple files and return `ingested_count` |
| Lead upload | Frontend expected `lead_ids`; backend returned a list | Return `ingested_count` and `lead_ids` |
| Fit score | Frontend expected High/Medium/Low; backend stored 0–100 | High/Medium/Low plus confidence |
| Lead detail | Frontend expected research, evidence, explanation, and drafts | Persist and return all fields |
| Agents | Agent imports and backend stubs differed | Real agents live in `backend/app/agents` |
| Groq | Agent expected `get_completion`; backend exposed `call_groq` | Support both interfaces |
| RAG | Separate RAG was not routed | Connect parsing/indexing to upload and retrieval to analysis |
| Approval | Frontend sent approve/edit/reject; backend allowed approved/rejected | Normalize decisions and save edits |
| Docker | Frontend was disabled | Start both services |

## Ownership after integration

| Owner | Area | Immediate responsibility |
|---|---|---|
| Person 1 | Integration/backend | API contracts, merges, database |
| Person 2 | RAG | Retrieval quality and evidence |
| Person 3 | Agents | Prompts, JSON, hallucination checks |
| Person 4 | Frontend | UX and API communication |
| Person 5 | QA/data | End-to-end and failure tests |
| Person 6 | Demo/product | Story, slides, rehearsal, backup video |

Freeze new features until this works on every machine:

`Portfolio → Lead CSV → Analyze → Evidence → Fit → Drafts → Edit/Approve/Reject`
