"""
Research Agent

Summarizes a lead's company and infers likely needs, using strictly the
lead's CSV row and a web excerpt provided by the caller. Never invents
company facts.
"""

from typing import Any, Mapping

from app.agents._utils import run_json_agent
from app.schemas import ResearchOutput

SYSTEM_PROMPT = (
    "You are a B2B research analyst. You are given raw data about a company: "
    "a CSV row describing a sales lead, and an excerpt of text scraped from "
    "the company's website or public profile. Using ONLY the information "
    "provided, produce a concise company summary and a list of the "
    "company's likely needs.\n\n"
    "Strict rules:\n"
    "- Do not invent facts, numbers, products, employees, or details that "
    "are not present in the provided data.\n"
    "- If the provided data is insufficient to determine something, omit "
    "it rather than guessing.\n"
    "- 'evidence_sources' must only reference material you were actually "
    "given (e.g. the lead_csv_row field name, or a short excerpt/paraphrase "
    "from web_excerpt) - never a source you were not given.\n"
    "- Respond with ONLY a single valid JSON object, no markdown, no "
    "commentary, no code fences, matching exactly this schema:\n"
    '{"company_summary": string, "likely_needs": [string, ...], '
    '"evidence_sources": [string, ...]}'
)

_FALLBACK = ResearchOutput(
    company_summary=(
        "Unable to generate a verified company summary from the provided data."
    ),
    likely_needs=[],
    evidence_sources=[],
)


def run_research_agent(
    lead_csv_row: Mapping[str, Any],
    web_excerpt: str,
) -> ResearchOutput:
    """
    Args:
        lead_csv_row: One row of lead data (e.g. a dict from the leads CSV -
            company name, industry, contact info, etc).
        web_excerpt: Raw text excerpt scraped from the lead's website or
            public profile.

    Returns:
        A validated ResearchOutput. If the model fails to produce valid
        JSON after one retry, a schema-valid fallback is returned instead
        of raising.
    """
    user_prompt = (
        "lead_csv_row:\n"
        f"{dict(lead_csv_row)}\n\n"
        "web_excerpt:\n"
        f"{web_excerpt}\n\n"
        "Produce company_summary, likely_needs, and evidence_sources as "
        "instructed above."
    )

    return run_json_agent(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_cls=ResearchOutput,
        fallback=_FALLBACK,
    )
