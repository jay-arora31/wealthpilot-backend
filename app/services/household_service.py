import uuid

from fastapi import HTTPException

from app.repositories.conflict_repo import ConflictRepository
from app.repositories.household_repo import HouseholdRepository
from app.schemas.household import HouseholdCreate, HouseholdDetail, HouseholdSummary, HouseholdUpdate


class HouseholdService:
    def __init__(self, repo: HouseholdRepository, conflict_repo: ConflictRepository) -> None:
        self.repo = repo
        self.conflict_repo = conflict_repo

    async def list_households(self) -> list[HouseholdSummary]:
        rows = await self.repo.list_with_member_counts()
        return [
            HouseholdSummary(
                id=h.id,
                name=h.name,
                income=h.income,
                net_worth=h.net_worth,
                member_count=count,
            )
            for h, count in rows
        ]

    async def get_household(self, id: uuid.UUID) -> HouseholdDetail:
        household = await self.repo.get_by_id_with_relations(id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")
        pending_count = await self.conflict_repo.count_pending(id)

        from app.schemas.account import AccountResponse, OwnershipResponse
        from app.schemas.bank_detail import BankDetailResponse
        from app.schemas.member import MemberResponse

        members = [MemberResponse.model_validate(m) for m in household.members]
        accounts = []
        for acc in household.financial_accounts:
            ownerships = []
            for o in acc.ownerships:
                member_name = None
                for m in household.members:
                    if m.id == o.member_id:
                        member_name = m.name
                        break
                ownerships.append(
                    OwnershipResponse(
                        id=o.id,
                        member_id=o.member_id,
                        ownership_percentage=o.ownership_percentage,
                        member_name=member_name,
                    )
                )
            accounts.append(
                AccountResponse(
                    id=acc.id,
                    household_id=acc.household_id,
                    account_number=acc.account_number,
                    custodian=acc.custodian,
                    account_type=acc.account_type,
                    account_value=acc.account_value,
                    ownerships=ownerships,
                )
            )
        bank_details = [BankDetailResponse.model_validate(bd) for bd in household.bank_details]

        return HouseholdDetail(
            id=household.id,
            name=household.name,
            income=household.income,
            net_worth=household.net_worth,
            liquid_net_worth=household.liquid_net_worth,
            expense_range=household.expense_range,
            tax_bracket=household.tax_bracket,
            risk_tolerance=household.risk_tolerance,
            time_horizon=household.time_horizon,
            goals=household.goals,
            preferences=household.preferences,
            members=members,
            financial_accounts=accounts,
            bank_details=bank_details,
            pending_conflict_count=pending_count,
            created_at=household.created_at,
            updated_at=household.updated_at,
        )

    async def create_household(self, data: HouseholdCreate):
        return await self.repo.create(data)

    async def update_household(self, id: uuid.UUID, data: HouseholdUpdate):
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        household = await self.repo.update(id, update_dict)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")
        return household

    async def delete_household(self, id: uuid.UUID) -> None:
        household = await self.repo.get_by_id(id)
        if not household:
            raise HTTPException(status_code=404, detail="Household not found")
        await self.repo.delete(id)
