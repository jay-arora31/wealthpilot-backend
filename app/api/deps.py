from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.account_repo import AccountRepository
from app.repositories.bank_detail_repo import BankDetailRepository
from app.repositories.conflict_repo import ConflictRepository
from app.repositories.household_repo import HouseholdRepository
from app.repositories.insight_repo import InsightRepository
from app.repositories.member_repo import MemberRepository
from app.services.admin_service import AdminService
from app.services.audio_service import AudioService
from app.services.conflict_service import ConflictService
from app.services.excel_service import ExcelService
from app.services.household_service import HouseholdService
from app.services.insight_service import InsightService
from app.services.member_service import MemberService


async def get_household_repo(db: AsyncSession = Depends(get_db)) -> HouseholdRepository:
    return HouseholdRepository(db)


async def get_member_repo(db: AsyncSession = Depends(get_db)) -> MemberRepository:
    return MemberRepository(db)


async def get_account_repo(db: AsyncSession = Depends(get_db)) -> AccountRepository:
    return AccountRepository(db)


async def get_bank_detail_repo(db: AsyncSession = Depends(get_db)) -> BankDetailRepository:
    return BankDetailRepository(db)


async def get_conflict_repo(db: AsyncSession = Depends(get_db)) -> ConflictRepository:
    return ConflictRepository(db)


async def get_conflict_service(
    conflict_repo: ConflictRepository = Depends(get_conflict_repo),
    household_repo: HouseholdRepository = Depends(get_household_repo),
    member_repo: MemberRepository = Depends(get_member_repo),
) -> ConflictService:
    return ConflictService(conflict_repo, household_repo, member_repo)


async def get_household_service(
    household_repo: HouseholdRepository = Depends(get_household_repo),
    conflict_repo: ConflictRepository = Depends(get_conflict_repo),
) -> HouseholdService:
    return HouseholdService(household_repo, conflict_repo)


async def get_member_service(
    member_repo: MemberRepository = Depends(get_member_repo),
) -> MemberService:
    return MemberService(member_repo)


async def get_excel_service(
    household_repo: HouseholdRepository = Depends(get_household_repo),
    member_repo: MemberRepository = Depends(get_member_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
    bank_detail_repo: BankDetailRepository = Depends(get_bank_detail_repo),
    conflict_service: ConflictService = Depends(get_conflict_service),
) -> ExcelService:
    return ExcelService(household_repo, member_repo, account_repo, bank_detail_repo, conflict_service)


async def get_audio_service(
    household_repo: HouseholdRepository = Depends(get_household_repo),
    conflict_service: ConflictService = Depends(get_conflict_service),
    member_repo: MemberRepository = Depends(get_member_repo),
    account_repo: AccountRepository = Depends(get_account_repo),
) -> AudioService:
    return AudioService(household_repo, conflict_service, member_repo, account_repo)


async def get_insight_repo(db: AsyncSession = Depends(get_db)) -> InsightRepository:
    return InsightRepository(db)


async def get_insight_service(
    repo: InsightRepository = Depends(get_insight_repo),
) -> InsightService:
    return InsightService(repo)


async def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(db)
