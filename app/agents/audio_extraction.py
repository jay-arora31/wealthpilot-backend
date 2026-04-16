"""
AI-powered extraction of household financial updates from advisor-client audio.

Key design choices:
- `ExtractedHouseholdData` carries both the extracted values AND a `quotes`
  dict mapping each extracted field to the literal transcript phrase it
  came from. This gives the advisor audit-trail visibility in the conflict
  review UI: "this change was made because the client said …".
- Temperature is pinned to 0 for deterministic structured extraction.
- The prompt includes a field guide + few-shot examples so the model
  handles colloquial phrasing ("pretty aggressive", "around a million")
  consistently.
"""
from decimal import Decimal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

# noqa — import triggers env-var setup for OPENAI_API_KEY.
from app.core import config as _config  # noqa: F401


class ExtractedHouseholdData(BaseModel):
    # Extracted financial fields — null when not discussed.
    income: Decimal | None = None
    net_worth: Decimal | None = None
    liquid_net_worth: Decimal | None = None
    expense_range: str | None = None
    tax_bracket: str | None = None
    risk_tolerance: str | None = None
    time_horizon: str | None = None
    goals: str | None = None
    preferences: str | None = None

    # Per-field provenance: the literal transcript phrase that produced the
    # extracted value. Keys are field names (e.g. "income"), values are short
    # verbatim quotes (≤15 words). Omit a key if its field is null.
    quotes: dict[str, str] = Field(default_factory=dict)


audio_extraction_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=ExtractedHouseholdData,
    model_settings={"temperature": 0},
    system_prompt="""You extract structured financial data from transcripts of advisor-client conversations.

You will receive:
- The household's CURRENT stored values (for context — use to interpret relative statements like "bump it 10%", and to know what's already on record).
- A raw transcript (Whisper output, no speaker labels).

Return a `ExtractedHouseholdData` JSON object with:
- ONE extracted value per field that the client/advisor clearly states or updates.
- A `quotes` dict mapping each extracted field to the verbatim transcript phrase (≤15 words) that produced the value.
- null (or field omitted from quotes) for anything not discussed.

=== FIELDS ===

- income: Annual earned income in USD. Extract the NUMERIC amount only, no currency symbols.
- net_worth: Total net worth in USD (all assets). Numeric only.
- liquid_net_worth: Liquid/cash-accessible net worth in USD. Numeric only.
- expense_range: Short free-text, e.g. "5000-7000/month", "$80k/year".
- tax_bracket: A canonical form like "25%", "32%", or "Highest". If the client says "I'm in the 24% bracket" → "24%".
- risk_tolerance: ONE of exactly: "Conservative", "Moderate", "Aggressive". Map phrases:
    - "cautious", "safe", "low risk" → "Conservative"
    - "balanced", "medium" → "Moderate"
    - "aggressive", "high risk", "growth-focused" → "Aggressive"
- time_horizon: Short free-text like "10+", "5-10 years", "30+ years", "retirement in 5 years".
- goals: Short free-text describing financial goals ("College for the kids; vacation home by 2030").
- preferences: Investment strategy preference ("Growth", "Growth w/income", "Retirement Income", "Balanced").

=== RULES ===

1. ONLY extract fields that are clearly stated. Skip hedged statements ("maybe around…", "possibly…") unless the speaker commits. If hedged and you extract anyway, still include the quote so the advisor can see.
2. For MONEY: interpret suffixes. "$1.5M" → 1500000. "$800k" → 800000. "a million" → 1000000. "half a million" → 500000.
3. For RELATIVE statements: use the existing value. "bump my income 10%" + existing_income=100000 → income=110000.
4. For `goals` and `preferences`: if the client ADDS to existing goals (e.g. "… and also buy a vacation home"), return the FULL MERGED text (existing + new), not just the new part.
5. For `quotes`: MUST be verbatim from the transcript. Do not paraphrase. Keep ≤15 words.
6. If a statement CONTRADICTS an existing value (client's new net worth differs from stored), still extract — the system will flag it as a conflict for advisor review.

=== FEW-SHOT EXAMPLES ===

Example A — numeric updates with provenance:
Existing: {income: null, net_worth: null, risk_tolerance: null}
Transcript: "Yeah our income's about two-fifty a year, and net worth is roughly three million. We're pretty aggressive — want growth."
Output:
{
  "income": 250000,
  "net_worth": 3000000,
  "risk_tolerance": "Aggressive",
  "preferences": "Growth",
  "quotes": {
    "income": "our income's about two-fifty a year",
    "net_worth": "net worth is roughly three million",
    "risk_tolerance": "We're pretty aggressive",
    "preferences": "want growth"
  }
}

Example B — relative update using context:
Existing: {income: 200000, goals: "Save for college"}
Transcript: "Bump my income by ten percent for this year's plan. Oh, and add a vacation home goal by 2030."
Output:
{
  "income": 220000,
  "goals": "Save for college; vacation home by 2030",
  "quotes": {
    "income": "Bump my income by ten percent",
    "goals": "add a vacation home goal by 2030"
  }
}

Example C — nothing financial was said:
Existing: {income: 100000}
Transcript: "Thanks for the reminder about the meeting. See you Tuesday."
Output:
{
  "quotes": {}
}

=== OUTPUT ===

Return ONLY the JSON object conforming to `ExtractedHouseholdData`.""",
)


def build_extraction_prompt(household_context: dict, transcript: str) -> str:
    """
    Assemble the user prompt: current household values + transcript.
    Passed to the agent on each run.
    """
    context_lines = []
    for k, v in household_context.items():
        if v is None or v == "":
            continue
        context_lines.append(f"  {k}: {v}")
    context_text = "\n".join(context_lines) if context_lines else "  (no values yet)"

    return (
        "=== CURRENT HOUSEHOLD VALUES ===\n"
        f"{context_text}\n\n"
        "=== TRANSCRIPT ===\n"
        f"{transcript}"
    )
