import logfire
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import jobs as job_store
from app.models.database import (
    AccountOwnership,
    BankDetail,
    DataConflict,
    FinancialAccount,
    Household,
    Member,
)


class AdminService:
    """Destructive, app-wide admin operations (resetting data, etc.)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @logfire.instrument("admin.delete_all_data")
    async def delete_all_data(self) -> dict:
        """Wipe every domain row. Uses bulk DELETEs in dependency order — the
        DB's foreign keys don't have ON DELETE CASCADE at the schema level,
        so we can't rely on cascading from `households`."""
        # Order matters: leaves first, roots last.
        await self.db.execute(delete(AccountOwnership))
        await self.db.execute(delete(DataConflict))
        await self.db.execute(delete(BankDetail))
        await self.db.execute(delete(FinancialAccount))
        await self.db.execute(delete(Member))
        result = await self.db.execute(delete(Household))
        await self.db.commit()
        deleted = result.rowcount or 0

        # Clear the in-memory background job log so the UI doesn't keep
        # referencing jobs tied to data that no longer exists.
        job_store._jobs.clear()
        logfire.info("admin.deleted_all_data", households_deleted=deleted)
        return {"households_deleted": deleted}
