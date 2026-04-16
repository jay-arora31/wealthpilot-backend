from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import FinancialAccount, Household, Member
from app.schemas.insight import (
    AccountDistribution,
    IncomeExpenseItem,
    LiquidityRatio,
    MembersPerHousehold,
    NetWorthBreakdown,
    RiskToleranceDistribution,
    TaxBracketDistribution,
    TopHouseholdByWealth,
)


class InsightRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def income_vs_expenses(self) -> list[IncomeExpenseItem]:
        result = await self.db.execute(select(Household))
        households = list(result.scalars().all())
        return [
            IncomeExpenseItem(
                household_id=h.id,
                household_name=h.name,
                income=h.income,
                expense_range=h.expense_range,
            )
            for h in households
        ]

    async def net_worth_breakdown(self) -> list[NetWorthBreakdown]:
        result = await self.db.execute(select(Household))
        households = list(result.scalars().all())
        return [
            NetWorthBreakdown(
                household_id=h.id,
                household_name=h.name,
                net_worth=h.net_worth,
                liquid_net_worth=h.liquid_net_worth,
            )
            for h in households
        ]

    async def account_distribution(self) -> list[AccountDistribution]:
        result = await self.db.execute(
            select(
                FinancialAccount.account_type,
                func.sum(FinancialAccount.account_value).label("total_value"),
                func.count(FinancialAccount.id).label("count"),
            )
            .where(FinancialAccount.account_type.isnot(None))
            .group_by(FinancialAccount.account_type)
        )
        return [
            AccountDistribution(
                account_type=row.account_type,
                total_value=Decimal(str(row.total_value or 0)),
                count=row.count,
            )
            for row in result.all()
        ]

    async def members_per_household(self) -> list[MembersPerHousehold]:
        result = await self.db.execute(
            select(
                Household.id,
                Household.name,
                func.count(Member.id).label("member_count"),
            )
            .outerjoin(Member, Member.household_id == Household.id)
            .group_by(Household.id, Household.name)
        )
        return [
            MembersPerHousehold(
                household_id=row.id,
                household_name=row.name,
                member_count=row.member_count,
            )
            for row in result.all()
        ]

    async def tax_bracket_distribution(self) -> list[TaxBracketDistribution]:
        result = await self.db.execute(
            select(
                Household.tax_bracket,
                func.count(Household.id).label("household_count"),
            )
            .where(Household.tax_bracket.isnot(None))
            .group_by(Household.tax_bracket)
            .order_by(Household.tax_bracket)
        )
        return [
            TaxBracketDistribution(
                tax_bracket=row.tax_bracket,
                household_count=row.household_count,
            )
            for row in result.all()
        ]

    async def risk_tolerance_distribution(self) -> list[RiskToleranceDistribution]:
        result = await self.db.execute(
            select(
                Household.risk_tolerance,
                func.count(Household.id).label("household_count"),
            )
            .where(Household.risk_tolerance.isnot(None))
            .group_by(Household.risk_tolerance)
            .order_by(func.count(Household.id).desc())
        )
        return [
            RiskToleranceDistribution(
                risk_tolerance=row.risk_tolerance,
                household_count=row.household_count,
            )
            for row in result.all()
        ]

    async def top_households_by_wealth(self, limit: int = 10) -> list[TopHouseholdByWealth]:
        result = await self.db.execute(
            select(Household)
            .where(Household.net_worth.isnot(None))
            .order_by(Household.net_worth.desc())
            .limit(limit)
        )
        return [
            TopHouseholdByWealth(
                household_id=h.id,
                household_name=h.name,
                net_worth=h.net_worth,
                liquid_net_worth=h.liquid_net_worth or Decimal(0),
                income=h.income or Decimal(0),
            )
            for h in result.scalars().all()
        ]

    async def liquidity_ratios(self) -> list[LiquidityRatio]:
        result = await self.db.execute(select(Household))
        ratios = []
        for h in result.scalars().all():
            if h.net_worth and h.liquid_net_worth and h.net_worth > 0:
                ratio = float(h.liquid_net_worth / h.net_worth * 100)
                ratios.append(LiquidityRatio(
                    household_id=h.id,
                    household_name=h.name,
                    liquid_ratio=round(ratio, 1),
                ))
        return sorted(ratios, key=lambda r: r.liquid_ratio, reverse=True)
