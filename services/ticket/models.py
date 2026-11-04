
import uuid

from sqlalchemy import Column, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from services.ticket.database import Base


class Ticket(Base):
    __tablename__ = "ticket"

    id = Column(Integer, primary_key=True, index=True)

    ticket_uid = Column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        default=uuid.uuid4
    )

    username = Column(String(80), nullable=False)
    flight_number = Column(String(20), nullable=False)
    price = Column(Integer, nullable=False)

    status = Column(
        String(20),
        nullable=False,
        default="PAID"
    )
