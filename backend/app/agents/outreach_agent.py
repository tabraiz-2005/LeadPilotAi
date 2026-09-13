"""
Outreach Agent

Drafts a personalized outreach email and LinkedIn message from the research
and fit-assessment evidence already gathered, referencing 1-2 real
portfolio items and nothing invented.
"""

from typing import Union

from app.agents._utils import run_json_agent
from app.schemas import FitScoreOutput, OutreachOutput, ResearchOutput

SYSTEM_PROMPT = (
    "You are a freelance business-development copywriter. You are given "
    "research about a prospective client (research_output), a fit "
    "assessment explaining why a freelancer suits this lead (fit_output), "
    "and evidence of the freelancer's past work (portfolio_evidence).\n\n"
    "Write a concise, personalized cold email draft and a shorter LinkedIn "
    "outreach message draft.\n\n"
    "Strict rules:\n"
    "- Use only facts present in research_output, fit_output, and "
    "portfolio_evidence. Do not invent company details, results, metrics, "
    "or portfolio items.\n"
    "- Reference exactly 1-2 relevant portfolio items from portfolio_evidence "
    "in the messages - never more, and never ones that aren't in the input.\n"
    "- Keep email_draft short (roughly 100-150 words) and linkedin_draft "
    "even shorter (roughly 40-60 words).\n"
    "- 'rag_evidence_summary' must briefly list which specific pieces of "
    "evidence (from research_output / portfolio_evidence) were used to "
    "personalize the drafts.\n"
    "- Respond with ONLY a single valid JSON object, no markdown, no "
    "commentary, no code fences, matching exactly this schema:\n"
    '{"email_draft": string, "linkedin_draft": string, '
    '"rag_evidence_summary": string}'
)

_FALLBACK = OutreachOutput(
    email_draft="",
    linkedin_draft="",
    rag_evidence_summary="Unable to generate outreach drafts from the provided data.",
)


def run_outreach_agent(
    research_output: Union[ResearchOutput, dict],
    fit_output: Union[FitScoreOutput, dict],
    portfolio_evidence: str,
) -> OutreachOutput:
    """
    Args:
        research_output: Output of run_research_agent (ResearchOutput or an
            equivalent dict).
        fit_output: Output of run_fit_scorer_agent (FitScoreOutput or an
            equivalent dict).
        portfolio_evidence: Raw text describing relevant past work/portfolio
            items available to reference.

    Returns:
        A validated OutreachOutput. If the model fails to produce valid
        JSON after one retry, a schema-valid fallback is returned instead
        of raising.
    """
    if isinstance(research_output, ResearchOutput):
        research_output = research_output.model_dump()
    if isinstance(fit_output, FitScoreOutput):
        fit_output = fit_output.model_dump()

    user_prompt = (
        "research_output:\n"
        f"{research_output}\n\n"
        "fit_output:\n"
        f"{fit_output}\n\n"
        "portfolio_evidence:\n"
        f"{portfolio_evidence}\n\n"
        "Produce email_draft, linkedin_draft, and rag_evidence_summary as "
        "instructed above."
    )

    return run_json_agent(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_cls=OutreachOutput,
        fallback=_FALLBACK,
    )
