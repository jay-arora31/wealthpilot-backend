"""
AI-powered extraction of household data from advisor-client audio.

Design:
- `ExtractedHouseholdData` captures three layers of information:
    1. Household-level financials (income, net_worth, risk_tolerance, …)
    2. `members` — the people in the household (name, DOB, email, phone, …)
    3. `financial_accounts` — investment / real-estate / cash accounts mentioned
  This mirrors the shape the Excel ingestion pipeline already writes, so
  audio and Excel can feed the same domain objects.
- `quotes` carries per-field provenance for the household-level fields so
  the advisor sees WHY a change was proposed in the conflict review UI.
  Members/accounts each carry their own `source_quote`.
- Temperature is pinned to 0 for deterministic structured extraction.
"""
from decimal import Decimal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

# noqa — import triggers env-var setup for OPENAI_API_KEY.
from app.core import config as _config  # noqa: F401


class ExtractedMember(BaseModel):
    """A person discussed in the conversation."""

    name: str
    date_of_birth: str | None = None
    email: str | None = None
    phone: str | None = None
    member_relationship: str | None = None  # "self" | "spouse" | "son" | "daughter" | …
    address: str | None = None
    source_quote: str | None = None  # ≤15 verbatim words


class ExtractedAccount(BaseModel):
    """A financial account or real-estate / income-generating asset mentioned."""

    custodian: str | None = None  # e.g. "Dell 401k", "Schwab", "Downtown Austin rental"
    account_type: str | None = None  # e.g. "401k", "Brokerage", "Rental Property", "Checking"
    account_number: str | None = None
    account_value: Decimal | None = None
    # Names (as spoken in the transcript) of members who own this account; the
    # service resolves them to member IDs after the members themselves are
    # persisted. Empty if ownership isn't clearly stated.
    owner_names: list[str] = Field(default_factory=list)
    source_quote: str | None = None


class ExtractedHouseholdData(BaseModel):
    # ── Household-level financials — null when not discussed ──────────
    income: Decimal | None = None
    net_worth: Decimal | None = None
    liquid_net_worth: Decimal | None = None
    expense_range: str | None = None
    tax_bracket: str | None = None
    risk_tolerance: str | None = None  # "Conservative" | "Moderate" | "Aggressive"
    time_horizon: str | None = None     # e.g. "8-14 years"
    goals: str | None = None
    preferences: str | None = None

    # Per-field provenance for the household-level fields above. Keys are
    # field names; values are short verbatim transcript quotes (≤15 words).
    # Omit a key if its field is null.
    quotes: dict[str, str] = Field(default_factory=dict)

    # ── Structured people + accounts ─────────────────────────────────
    members: list[ExtractedMember] = Field(default_factory=list)
    financial_accounts: list[ExtractedAccount] = Field(default_factory=list)


audio_extraction_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=ExtractedHouseholdData,
    model_settings={"temperature": 0},
    system_prompt="""You extract structured household data from transcripts of advisor-client conversations.

You will receive:
- The household's CURRENT stored values (context — use to interpret relative statements like "bump it 10%", and to know what's already on record).
- A raw transcript (Whisper output, no speaker labels).

Return an `ExtractedHouseholdData` JSON object with three layers:

1. HOUSEHOLD-LEVEL financial fields (scalar values on the household row).
2. `members` — a list of every PERSON the conversation describes (the client, spouse, children). Capture name, DOB if stated, email, phone, relationship, address.
3. `financial_accounts` — a list of every ACCOUNT or income-generating asset mentioned (401k, brokerage, rental property, bank accounts, etc.). Real-estate that generates income counts as an account (account_type = "Rental Property"). The rental's `account_value` is the PROPERTY value if stated; otherwise leave null. Monthly rental income belongs in household `expense_range`/notes, NOT in `account_value`.

=== HOUSEHOLD FIELDS ===

- income: Annual earned income in USD. NUMERIC only, no currency symbols. Include only EARNED comp (salary + bonus); do NOT fold rental income or investment income into this.
- net_worth: Total net worth in USD (all assets). Numeric only.
- liquid_net_worth: Liquid/cash-accessible net worth in USD. Numeric only.
- expense_range: Short free-text, e.g. "5000-7000/month", "$80k/year".
- tax_bracket: A canonical form like "25%", "32%", "Highest". Extract only when stated.
- risk_tolerance: EXACTLY ONE of: "Conservative", "Moderate", "Aggressive". Mapping rules:
    - "cautious", "safe", "low risk" → "Conservative"
    - "balanced", "medium" → "Moderate"
    - "aggressive", "high risk", "growth-focused" → "Aggressive"
    - Hedged spans like "conservative to moderate" or "moderate to aggressive" → pick the HIGHER end ("Moderate", "Aggressive" respectively). Rationale: the client is signalling tolerance up to that level.
- time_horizon: A DURATION, not a literal target age. If the client says "retire at 62-65" and is age 51, return "11-14 years". If age is unknown, return a short descriptor like "10-15 years to retirement". NEVER return a raw age-based phrase like "Retirement at 62-65".
- goals: Free-text, semicolon-separated list. If client ADDS a goal, MERGE with the existing goals (existing + "; " + new). Keep each goal short.
- preferences: Investment strategy preferences + notable planning concerns the client raised (e.g. "Tax-efficient investing", "Estate planning", "Cash-flow optimization", "Growth w/income"). Semicolon-separated list. If new items appear and existing preferences are stored, MERGE them (existing + "; " + new items, deduped).

=== MEMBERS ===

- Include the client themselves (relationship = "self"), spouse, children, anyone explicitly described as part of the household or with personal data disclosed.
- Name: prefer the name the person GOES BY professionally. Ignore full legal names in parentheses unless only that is given.
  Example: "Benjamin Walter Thompson Jr., but he goes by Benjamin" → name = "Benjamin Walter".
  If the transcript uses first+middle as the working name (e.g. "Benjamin Walter"), keep that.
- date_of_birth: Convert to ISO (YYYY-MM-DD) only if BOTH month/day AND year are known. If only the month/day are stated and age is given, compute the year from age (assume today's year as the reference for "birthday on <date>"). If uncertain, leave null.
- email: prefer the personal email the client says they use for advisor communications. Convert " at " → "@" and " dot " / " slash " back to "." / "/" if spoken.
- phone: normalise digits + dashes only, e.g. "512-555-3847".
- member_relationship: "self" | "spouse" | "son" | "daughter" | "partner" | …
- address: the residence; include street, city, state, zip when stated.
- Only add a member if the transcript gives at least a NAME.

=== ACCOUNTS ===

- Include EVERY account the transcript mentions, even without dollar amounts. If the client says "I have my 401k, some real estate, and a stock portfolio," emit THREE separate account entries (401k, Rental Property, Individual Stocks). Do NOT skip an account just because its value or custodian wasn't stated.
- custodian: the institution if named (e.g. "Dell", "Schwab"); for a rental property, a short descriptor ("Downtown Austin rental"). If the employer's name is mentioned alongside a 401(k) (e.g. "his Dell 401k" or "worked 12 years at Dell … he has a 401k"), set custodian to the employer.
- account_type: "401k", "IRA", "Brokerage", "Individual Stocks", "Rental Property", "Checking", "Savings", etc.
- account_number: only if stated. Leave null otherwise.
- account_value: numeric if stated; otherwise null.
- owner_names: names (as used for the members list) of the owners. Leave empty if unclear.
- source_quote: ≤15 verbatim words from the transcript.
- If the transcript only mentions alimony/child-support PAYMENTS (outflows), do NOT add them as accounts — surface that context in `expense_range` or `preferences` instead.

=== QUOTES (household level) ===

- `quotes` is a dict mapping each extracted household-level field (income, net_worth, …) to the verbatim transcript phrase that produced it (≤15 words). Do NOT paraphrase. Omit keys for fields you didn't extract.

=== RULES ===

1. ONLY extract values that are clearly stated. Skip hedged statements ("maybe around…", "possibly…") unless the speaker commits.
2. MONEY suffixes: "$1.5M" → 1500000. "$800k" → 800000. "a million" → 1000000. "half a million" → 500000.
3. RELATIVE statements: use the existing value. "bump my income 10%" + existing_income=100000 → income=110000.
4. MERGE goals and preferences with existing values — do not replace. Dedupe and keep the list concise.
5. If a statement CONTRADICTS an existing value, still extract — the system will flag it as a conflict for review.
6. When the client is a NEW prospect with no existing household values, populate everything you can; don't assume "no prior record → extract less".

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
  },
  "members": [],
  "financial_accounts": []
}

Example B — new prospect, members + accounts:
Existing: (no values yet)
Transcript: "New client, Jane Doe, age 45. She's at 1200 Main St, Austin TX. Email jane@acme.com. She has a Schwab brokerage worth around 400k, and a Chase 401k from her old job. Risk is moderate."
Output:
{
  "risk_tolerance": "Moderate",
  "quotes": { "risk_tolerance": "Risk is moderate" },
  "members": [
    {
      "name": "Jane Doe",
      "email": "jane@acme.com",
      "address": "1200 Main St, Austin, TX",
      "member_relationship": "self",
      "source_quote": "New client, Jane Doe, age 45"
    }
  ],
  "financial_accounts": [
    {
      "custodian": "Schwab",
      "account_type": "Brokerage",
      "account_value": 400000,
      "owner_names": ["Jane Doe"],
      "source_quote": "Schwab brokerage worth around 400k"
    },
    {
      "custodian": "Chase",
      "account_type": "401k",
      "owner_names": ["Jane Doe"],
      "source_quote": "Chase 401k from her old job"
    }
  ]
}

Example C — relative update:
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
