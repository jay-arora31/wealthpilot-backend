import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import relationship as sa_relationship


class Base(DeclarativeBase):
    pass


class Household(Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    income: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    net_worth: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    liquid_net_worth: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    expense_range: Mapped[str | None] = mapped_column(String, nullable=True)
    tax_bracket: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_tolerance: Mapped[str | None] = mapped_column(String, nullable=True)
    time_horizon: Mapped[str | None] = mapped_column(String, nullable=True)
    goals: Mapped[str | None] = mapped_column(String, nullable=True)
    preferences: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    members: Mapped[list["Member"]] = sa_relationship(
        "Member", back_populates="household", cascade="all, delete-orphan", lazy="selectin"
    )
    financial_accounts: Mapped[list["FinancialAccount"]] = sa_relationship(
        "FinancialAccount", back_populates="household", cascade="all, delete-orphan", lazy="selectin"
    )
    bank_details: Mapped[list["BankDetail"]] = sa_relationship(
        "BankDetail", back_populates="household", cascade="all, delete-orphan", lazy="selectin"
    )
    data_conflicts: Mapped[list["DataConflict"]] = sa_relationship(
        "DataConflict", back_populates="household", cascade="all, delete-orphan", lazy="noload"
    )


class Member(Base):
    __tablename__ = "members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    member_relationship: Mapped[str | None] = mapped_column("relationship", String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = sa_relationship("Household", back_populates="members")
    ownerships: Mapped[list["AccountOwnership"]] = sa_relationship(
        "AccountOwnership", back_populates="member", cascade="all, delete-orphan", lazy="selectin"
    )


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)
    account_number: Mapped[str | None] = mapped_column(String, nullable=True)
    custodian: Mapped[str | None] = mapped_column(String, nullable=True)
    account_type: Mapped[str | None] = mapped_column(String, nullable=True)
    account_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = sa_relationship("Household", back_populates="financial_accounts")
    ownerships: Mapped[list["AccountOwnership"]] = sa_relationship(
        "AccountOwnership", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )


class AccountOwnership(Base):
    __tablename__ = "account_ownerships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_accounts.id"), nullable=False
    )
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    ownership_percentage: Mapped[Decimal | None] = mapped_column(Numeric(7, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    account: Mapped["FinancialAccount"] = sa_relationship("FinancialAccount", back_populates="ownerships")
    member: Mapped["Member"] = sa_relationship("Member", back_populates="ownerships")


class BankDetail(Base):
    __tablename__ = "bank_details"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String, nullable=True)
    account_number: Mapped[str | None] = mapped_column(String, nullable=True)
    routing_number: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    household: Mapped["Household"] = sa_relationship("Household", back_populates="bank_details")


class DataConflict(Base):
    __tablename__ = "data_conflicts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    existing_value: Mapped[str | None] = mapped_column(String, nullable=True)
    incoming_value: Mapped[str | None] = mapped_column(String, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(
        sa.Enum("excel", "audio", name="conflict_source_enum"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        sa.Enum("pending", "accepted", "rejected", name="conflict_status_enum"),
        nullable=False,
        server_default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    household: Mapped["Household"] = sa_relationship("Household", back_populates="data_conflicts")
