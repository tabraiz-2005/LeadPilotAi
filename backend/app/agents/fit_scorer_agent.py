"""
Fit Scorer Agent

Qualitatively evaluates how well a freelancer fits a lead, based on skill
match, portfolio relevance, and industry fit - never a hard-coded formula.
"""

from typing import Union

from app.agents._utils import run_json_agent
from app.schemas import FitScoreOutput, ResearchOutput

SYSTEM_PROMPT = (
    "You are an experienced freelance business consultant. You are given "
    "research about a prospective client (research_output), evidence of a "
    "freelancer's past work (portfolio_evidence), and a summary of the "
    "freelancer's skills and experience (freelancer_summary).\n\n"
    "Make a holistic, qualitative judgment of fit by weighing:\n"
    "- skill match: how well freelancer_summary covers the lead's likely_needs\n"
    "- portfolio relevance: how relevant portfolio_evidence is to this specific lead\n"
    "- industry fit: how well the freelancer's experience fits the lead's industry/company\n\n"
    "Strict rules:\n"
    "- Base your judgment only on the information provided. Do not invent "
    "skills, experience, or portfolio items that were not given to you.\n"
    "- Do not use a numeric formula or point system - reason qualitatively, "
    "then choose the rating that best fits your reasoning.\n"
    "- 'fit_score' must be exactly one of: \"High\", \"Medium\", \"Low\".\n"
    "- 'confidence' must be a number between 0.0 and 1.0 reflecting how "
    "confident you are given how much evidence you actually have.\n"
    "- 'matching_skills' must only list skills that literally appear in "
    "freelancer_summary or portfolio_evidence.\n"
    "- Respond with ONLY a single valid JSON object, no markdown, no "
    "commentary, no code fences, matching exactly this schema:\n"
    '{"fit_score": "High|Medium|Low", "confidence": number, '
    '"explanation": string, "matching_skills": [string, ...]}'
)

_FALLBACK = FitScoreOutput(
    fit_score="Low",
    confidence=0.0,
    explanation="Unable to generate a fit assessment from the provided data.",
    matching_skills=[],
)


def run_fit_scorer_agent(
    research_output: Union[ResearchOutput, dict],
    portfolio_evidence: str,
    freelancer_summary: str,
) -> FitScoreOutput:
    """
    Args:
        research_output: Output of run_research_agent (ResearchOutput or an
            equivalent dict).
        portfolio_evidence: Raw text describing relevant past work/portfolio
            items available to reference.
        freelancer_summary: Raw text summarizing the freelancer's skills and
            experience.

    Returns:
        A validated FitScoreOutput. If the model fails to produce valid
        JSON after one retry, a schema-valid fallback is returned instead
        of raising.
    """
    if isinstance(research_output, ResearchOutput):
        research_output = research_output.model_dump()

    user_prompt = (
        "research_output:\n"
        f"{research_output}\n\n"
        "portfolio_evidence:\n"
        f"{portfolio_evidence}\n\n"
        "freelancer_summary:\n"
        f"{freelancer_summary}\n\n"
        "Produce fit_score, confidence, explanation, and matching_skills as "
        "instructed above."
    )

    return run_json_agent(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema_cls=FitScoreOutput,
        fallback=_FALLBACK,
    )
