"""SQLAlchemy 2 models. Every business entity carries ``organization_id``.

Password hashes live ONLY in ``UserCredential``; ``AppUser`` is the view-facing identity.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ROLE_ORG_ADMIN = "ORG_ADMIN"
ROLE_SUPERVISOR = "SUPERVISOR"
ROLE_TECHNICIAN = "TECHNICIAN"
ENVIRONMENTS = ("OUTDOOR", "INDOOR")


def _org_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("organization.id"), nullable=False, index=True)


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped[Organization] = relationship()
    credential: Mapped[Optional[UserCredential]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def can_manage_clients(self) -> bool:
        return self.role in (ROLE_ORG_ADMIN, ROLE_SUPERVISOR)


class UserCredential(Base):
    __tablename__ = "user_credential"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="credential")


class Client(Base):
    __tablename__ = "client"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(160))
    email: Mapped[Optional[str]] = mapped_column(String(160))
    phone: Mapped[Optional[str]] = mapped_column(String(40))
    address: Mapped[Optional[str]] = mapped_column(String(255))

    pools: Mapped[list[Pool]] = relationship(back_populates="client", order_by="Pool.name")


class Pool(Base):
    """Alberca. ``volume_liters`` is authoritative."""

    __tablename__ = "pool"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = _org_fk()
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    volume_liters: Mapped[float] = mapped_column(Float, nullable=False)
    environment: Mapped[str] = mapped_column(String(10), default="OUTDOOR", nullable=False)

    client: Mapped[Client] = relationship(back_populates="pools")
