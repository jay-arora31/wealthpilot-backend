"""
AI-powered column mapping with an AI-based review pass.

Flow:
1. `column_mapping_agent` proposes an initial mapping from headers + sample rows.
2. `mapping_reviewer_agent` audits the proposal against the same data and
   returns a corrected mapping.
3. `normalize_mapping()` applies two cheap structural fix-ups (no content
   validation): drop `member_name` when split first/last exist, and resolve
   duplicate column indices.

The reviewer replaces what used to be a large stack of keyword lists and
regex-shape validators. If the mapper is wrong, the reviewer catches it;
if both are wrong, the advisor catches it via the post-upload review UI.
"""
from pydantic import BaseModel
from pydantic_ai import Agent

# noqa — import triggers env-var setup for OPENAI_API_KEY.
from app.core import config as _config  # noqa: F401


class ColumnMapping(BaseModel):
    household_name: int | None = None
    income: int | None = None
    net_worth: int | None = None
    liquid_net_worth: int | None = None
    expense_range: int | None = None
    tax_bracket: int | None = None
    risk_tolerance: int | None = None
    time_horizon: int | None = None
    goals: int | None = None
    preferences: int | None = None
    member_name: int | None = None        # full name column (if combined)
    member_first_name: int | None = None  # first name column (if split)
    member_last_name: int | None = None   # last name column (if split)
    member_dob: int | None = None
    member_email: int | None = None
    member_phone: int | None = None
    member_relationship: int | None = None
    member_address: int | None = None
    account_number: int | None = None
    custodian: int | None = None
    account_type: int | None = None
    account_value: int | None = None
    ownership_percentage: int | None = None
    bank_name: int | None = None
    bank_account_number: int | None = None
    routing_number: int | None = None


_FIELD_GUIDE = """=== CANONICAL FIELDS AND WHAT TO LOOK FOR ===

HOUSEHOLD:
- household_name: Family/client group name shared across rows. Headers: "Household Name", "Family", "Client Name", "Group".

MEMBER (individual person):
- member_name: Single combined full-name column. Only set if first and last are NOT in separate columns.
- member_first_name: First/given name column. Headers: "First Name", "First", "Given Name".
- member_last_name: Last/family name column. Headers: "Last Name", "Last", "Surname".
- member_dob: Date of birth. Headers: "DOB", "Date of Birth", "Birth Date".
- member_email: Email. Must contain "@" in sample values.
- member_phone: Phone/mobile. Numeric values, usually 10+ digits.
- member_address: Street/mailing address.
- member_relationship: Relationship to primary OR marital status. Headers: "Relationship", "Relation", "Marital Status". Values like "Spouse", "Parent", "Married", "Single".

FINANCIAL:
- income: Annual earned income. Headers: "Annual Income", "Income", "Gross Income", "Earnings", "Annual Salary".
- net_worth: TOTAL net worth. Headers: "Total Net Worth", "Net Worth", "Total Assets", "Total Wealth". "Total Assets" = net_worth.
- liquid_net_worth: LIQUID portion only. Headers: "Liquid Net Worth", "Liquid Assets", "Cash Assets". "Liquid Assets" = liquid_net_worth, NOT net_worth.
- tax_bracket: Tax rate/bracket. Values can be decimals (0.25), percentages ("25%"), or strings ("Highest").
- risk_tolerance: Investment risk. Values: "Moderate", "Aggressive", "Conservative".
- time_horizon: Investment time horizon. Values: "10+", "5-10 years", "30+".
- goals: Specific financial goals. Headers: "Goals", "Financial Goals", "Primary Use of Funds".
- preferences: Investment strategy/objective. Headers: "Preferences", "Primary Investment Objective", "Strategy". Values: "Growth", "Growth w/income", "Retirement Income".
- expense_range: Monthly/annual expenses.

INVESTMENT ACCOUNT:
- account_type: Headers: "Account Type", "Acct Type". Values: "IRA", "Roth IRA", "Trust", "401k", "Joint".
- custodian: Brokerage. Values: "Goldman", "Fidelity", "NES".
- account_number: Investment/brokerage account number ONLY — sits near "Custodian"/"Account Type". If no such column exists, leave null.
- account_value: Current value of the investment account.
- ownership_percentage: Ownership % per member. NEVER map to "Beneficiary %" — that's a different concept.

BANKING:
- bank_name: Bank institution name. Values: "HDFC", "Chase", "Wells Fargo". CRITICAL: NEVER map "Marital Status" or a column whose values are "Married"/"Single"/"Divorced" here — those belong to member_relationship.
- bank_account_number: Bank account number — look for "Account No", "Bank Account Number", "Account Number" when that column sits in the banking section (near Bank Name / Bank Type). These are NOT investment account numbers.
- routing_number: Bank routing number — must be 9 digits.
"""


column_mapping_agent = Agent(
    "openai:gpt-4o",
    output_type=ColumnMapping,
    system_prompt=f"""You are an expert data mapping specialist for financial advisor client data.

Your job: given Excel column headers and sample rows, return the 0-based column index for each canonical field.
Return null for any field that has no matching column. Every index must be unique — do not map two fields to the same column.

{_FIELD_GUIDE}

=== FEW-SHOT EXAMPLES ===

Example A — split first/last + marital status:
Headers: ["Family", "First Name", "Last Name", "DOB", "Marital Status", "Income", "Total Assets", "Bank", "Routing #"]
Sample row: ["Smith", "John", "Smith", "1970-05-01", "Married", 150000, 1200000, "Chase", "021000021"]
Correct mapping:
  household_name=0, member_first_name=1, member_last_name=2, member_dob=3,
  member_relationship=4, income=5, net_worth=6, bank_name=7, routing_number=8
KEY INSIGHT: "Marital Status" → member_relationship, NOT bank_name. "Bank" (with value "Chase") → bank_name.

Example B — combined name + percentage tax:
Headers: ["Client Name", "Member", "Email", "Risk Tol", "Tax Bracket", "Liquid Assets", "Custodian", "Acct #", "Account Value"]
Sample row: ["Eggebraaten", "Steve Eggebraaten", "steve@x.com", "Moderate", 0.25, 800000, "Fidelity", "ABC-123", 500000]
Correct mapping:
  household_name=0, member_name=1, member_email=2, risk_tolerance=3,
  tax_bracket=4, liquid_net_worth=5, custodian=6, account_number=7, account_value=8
KEY INSIGHT: "Liquid Assets" → liquid_net_worth (NOT net_worth). 0.25 in tax_bracket means 25%.

Example C — banking section only:
Headers: ["Household", "Bank Name", "Bank Account Number", "Routing Number"]
Sample row: ["Johnson", "Wells Fargo", "864219753", "121000248"]
Correct mapping:
  household_name=0, bank_name=1, bank_account_number=2, routing_number=3
KEY INSIGHT: "Bank Account Number" → bank_account_number (NOT account_number — that's for investment accounts).

Example D — "Account No" adjacent to bank columns:
Headers: ["Household Name", "First Name", "Last Name", "Account Type", "Custodian", "Annual income", "Bank Name", "Bank Type - Checking/Savings", "Account No"]
Sample row: ["Smith", "John", "Smith", "IRA", "Fidelity", 120000, "HDFC", "Savings", "864219753"]
Correct mapping:
  household_name=0, member_first_name=1, member_last_name=2, account_type=3, custodian=4, income=5, bank_name=6, bank_account_number=8
KEY INSIGHT: "Account No" at column 8 sits in the banking section (next to "Bank Name", "Bank Type") and its value looks like a bank account number → bank_account_number, NOT account_number. account_number is for investment/brokerage account numbers and there is no such column here so it stays null.

=== RULES ===
1. Use sample row data to confirm your header interpretation — do not rely on headers alone.
2. If separate first/last columns exist, set member_first_name and member_last_name and leave member_name null.
3. account_number vs bank_account_number: these are DIFFERENT fields.
4. Every non-null index must be unique — no two fields can share the same column index.
5. Return null for any field with no clear matching column. Do not guess.""",
)


mapping_reviewer_agent = Agent(
    "openai:gpt-4o",
    output_type=ColumnMapping,
    system_prompt=f"""You are a data-mapping auditor. Another AI has proposed a column mapping for a financial advisor's Excel sheet. Your job is to return the FINAL corrected mapping.

You will receive:
1. The original headers.
2. Sample rows of actual data.
3. The proposed mapping as `field → column N ("Header")`.

{_FIELD_GUIDE}

=== YOUR REVIEW PROCEDURE ===

For EVERY proposed mapping, verify TWO things:
(a) Does the header semantically match the canonical field?
(b) Do the sample values in that column look like valid values for that field?

If either check fails, CORRECT the mapping:
- Move the field to the right column, OR
- Set the field to null if no column fits.

Also look for fields that were MISSED (left as null) but have an obvious column in the headers/samples, and fill them in.

=== COMMON MISTAKES TO CATCH ===

1. "Marital Status" (with values "Married"/"Single") mapped to bank_name. This is WRONG. Marital status → member_relationship. bank_name values look like "Chase", "HDFC", "Wells Fargo".
2. "Liquid Assets" mapped to net_worth. This is WRONG. "Liquid Assets" → liquid_net_worth. net_worth is the TOTAL (Total Assets, Total Net Worth).
3. "Beneficiary %" mapped to ownership_percentage. This is WRONG. Beneficiary ≠ ownership. Set ownership_percentage to null or to the real "Ownership %" column.
4. "Bank Account Number" or "Account No" mapped to account_number when it is clearly in the banking section (adjacent to "Bank Name", "Bank Type"). This is WRONG. Bank-account numbers go to bank_account_number; investment/brokerage account numbers go to account_number. If there is no dedicated investment account-number column, leave account_number as null.
5. routing_number mapped to a column whose values aren't 9 digits.
6. risk_tolerance and preferences swapped. risk_tolerance values look like "Moderate"/"Aggressive"/"Conservative". preferences values look like "Growth"/"Retirement Income"/"Growth w/income".
7. member_name set when member_first_name AND member_last_name are already separate columns. Drop member_name in that case.

=== RULES ===
1. Every non-null index must be unique across all fields.
2. Return null for any field with no clear match. Do not guess.
3. When in doubt, trust the SAMPLE VALUES over the header name.
4. Return the complete corrected mapping (all fields), not just the changes.""",
)


async def review_mapping(
    proposed: ColumnMapping,
    headers: list[str],
    sample_rows: list[list],
) -> ColumnMapping:
    """Run the reviewer agent to audit and correct a proposed mapping."""
    proposal_lines = []
    for field, idx in proposed.model_dump().items():
        if idx is None:
            proposal_lines.append(f"  {field} = null")
        elif idx < len(headers):
            proposal_lines.append(f'  {field} = col {idx} ("{headers[idx]}")')
        else:
            proposal_lines.append(f"  {field} = col {idx} (OUT OF RANGE)")
    proposal_text = "\n".join(proposal_lines)

    prompt = (
        f"Headers: {headers}\n"
        f"Sample rows: {sample_rows}\n\n"
        f"Proposed mapping:\n{proposal_text}\n\n"
        "Audit each mapping against the header and sample values. "
        "Return the final corrected mapping."
    )
    result = await mapping_reviewer_agent.run(prompt)
    return result.output


def normalize_mapping(mapping: ColumnMapping) -> ColumnMapping:
    """
    Cheap structural fix-ups that don't require content inspection:
      - Drop `member_name` when split first/last exist.
      - Resolve duplicate column indices by keeping the first claimant.
    """
    data = mapping.model_dump()

    if data.get("member_first_name") is not None or data.get("member_last_name") is not None:
        data["member_name"] = None

    seen: set[int] = set()
    for field, idx in list(data.items()):
        if idx is None:
            continue
        if idx in seen:
            data[field] = None
        else:
            seen.add(idx)

    return mapping.model_copy(update=data)


def mapping_to_display(mapping: ColumnMapping, headers: list[str]) -> list[dict]:
    """
    Flatten a ColumnMapping into a list of {field, header} pairs for UI display.
    Only includes fields that were actually mapped to a column.
    """
    out = []
    for field, idx in mapping.model_dump().items():
        if idx is None or idx >= len(headers):
            continue
        out.append({"field": field, "header": headers[idx], "column_index": idx})
    return out
