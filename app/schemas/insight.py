from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class IncomeExpenseItem(BaseModel):
    household_id: UUID
    household_name: str
    income: Decimal | None = None
    expense_range: str | None = None


class NetWorthBreakdown(BaseModel):
    household_id: UUID
    household_name: str
    net_worth: Decimal | None = None
    liquid_net_worth: Decimal | None = None


class AccountDistribution(BaseModel):
    account_type: str
    total_value: Decimal
    count: int


class MembersPerHousehold(BaseModel):
    household_id: UUID
    household_name: str
    member_count: int


class TaxBracketDistribution(BaseModel):
    tax_bracket: str
    household_count: int


class RiskToleranceDistribution(BaseModel):
    risk_tolerance: str
    household_count: int


class TopHouseholdByWealth(BaseModel):
    household_id: UUID
    household_name: str
    net_worth: Decimal
    liquid_net_worth: Decimal
    income: Decimal


class LiquidityRatio(BaseModel):
    household_id: UUID
    household_name: str
    liquid_ratio: float  # liquid_net_worth / net_worth as percentage


class InsightsResponse(BaseModel):
    income_vs_expenses: list[IncomeExpenseItem]
    net_worth: list[NetWorthBreakdown]
    account_distribution: list[AccountDistribution]
    members_per_household: list[MembersPerHousehold]
    tax_bracket_distribution: list[TaxBracketDistribution]
    risk_tolerance_distribution: list[RiskToleranceDistribution]
    top_households_by_wealth: list[TopHouseholdByWealth]
    liquidity_ratios: list[LiquidityRatio]
