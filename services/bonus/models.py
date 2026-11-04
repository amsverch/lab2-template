import uuid

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String
)
from sqlalchemy.dialects.postgresql import UUID

from services.bonus.database import Base


class Privilege(Base):
    __tablename__ = "privilege"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False, unique=True)
    status = Column(String(80), nullable=False, default="BRONZE")
    balance = Column(Integer, nullable=False, default=0)


class PrivilegeHistory(Base):
    __tablename__ = "privilege_history"

    id = Column(Integer, primary_key=True, index=True)
    privilege_id = Column(
        Integer,
        ForeignKey("privilege.id"),
        nullable=False
    )
    ticket_uid = Column(UUID(as_uuid=True), nullable=False)
    datetime = Column(DateTime, nullable=False, default=datetime.utcnow)
    balance_diff = Column(Integer, nullable=False)
    operation_type = Column(String(20), nullable=False)