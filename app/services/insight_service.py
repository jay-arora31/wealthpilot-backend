from app.repositories.insight_repo import InsightRepository
from app.schemas.insight import InsightsResponse


class InsightService:
    def __init__(self, repo: InsightRepository) -> None:
        self.repo = repo

    async def get_insights(self) -> InsightsResponse:
        income_vs_expenses = await self.repo.income_vs_expenses()
        net_worth = await self.repo.net_worth_breakdown()
        account_distribution = await self.repo.account_distribution()
        members_per_household = await self.repo.members_per_household()
        tax_bracket_distribution = await self.repo.tax_bracket_distribution()
        risk_tolerance_distribution = await self.repo.risk_tolerance_distribution()
        top_households_by_wealth = await self.repo.top_households_by_wealth()
        liquidity_ratios = await self.repo.liquidity_ratios()

        return InsightsResponse(
            income_vs_expenses=income_vs_expenses,
            net_worth=net_worth,
            account_distribution=account_distribution,
            members_per_household=members_per_household,
            tax_bracket_distribution=tax_bracket_distribution,
            risk_tolerance_distribution=risk_tolerance_distribution,
            top_households_by_wealth=top_households_by_wealth,
            liquidity_ratios=liquidity_ratios,
        )
