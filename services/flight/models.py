from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from services.flight.database import Base


class Airport(Base):
    __tablename__ = "airport"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255))
    city = Column(String(255))
    country = Column(String(255))


class Flight(Base):
    __tablename__ = "flight"

    id = Column(Integer, primary_key=True, index=True)
    flight_number = Column(String(20), nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False)
    from_airport_id = Column(Integer, ForeignKey("airport.id"))
    to_airport_id = Column(Integer, ForeignKey("airport.id"))
    price = Column(Integer, nullable=False)

    from_airport = relationship(
        "Airport",
        foreign_keys=[from_airport_id]
    )

    to_airport = relationship(
        "Airport",
        foreign_keys=[to_airport_id]
    )