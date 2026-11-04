from fastapi import Depends, FastAPI, HTTPException, Query
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Query
from sqlalchemy.orm import Session

from services.flight.database import Base, SessionLocal, engine, get_db
from services.flight.models import Airport, Flight


app = FastAPI(
    title="Flight Service",
    description="Service for searching flights",
    version="1.0.0"
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    seed_data()


def seed_data():
    """Добавляет тестовые аэропорты и рейс, если их ещё нет."""
    db = SessionLocal()

    try:
        # Ищем аэропорт Пулково.
        pulkovo = (
            db.query(Airport)
            .filter(
                Airport.name == "Пулково",
                Airport.city == "Санкт-Петербург"
            )
            .first()
        )

        if pulkovo is None:
            pulkovo = Airport(
                name="Пулково",
                city="Санкт-Петербург",
                country="Россия"
            )
            db.add(pulkovo)
            db.flush()

        # Ищем аэропорт Шереметьево.
        sheremetyevo = (
            db.query(Airport)
            .filter(
                Airport.name == "Шереметьево",
                Airport.city == "Москва"
            )
            .first()
        )

        if sheremetyevo is None:
            sheremetyevo = Airport(
                name="Шереметьево",
                city="Москва",
                country="Россия"
            )
            db.add(sheremetyevo)
            db.flush()

        # Проверяем, существует ли тестовый рейс.
        flight = (
            db.query(Flight)
            .filter(Flight.flight_number == "AFL031")
            .first()
        )

        if flight is None:
            flight = Flight(
                flight_number="AFL031",
                datetime=datetime(
                    2021, 10, 8, 20, 0,
                    tzinfo=timezone.utc
                ),
                from_airport_id=pulkovo.id,
                to_airport_id=sheremetyevo.id,
                price=1500
            )
            db.add(flight)

        db.commit()

    finally:
        db.close()


def format_flight(flight: Flight):
    return {
        "flightNumber": flight.flight_number,
        "fromAirport": (
            f"{flight.from_airport.city} "
            f"{flight.from_airport.name}"
        ),
        "toAirport": (
            f"{flight.to_airport.city} "
            f"{flight.to_airport.name}"
        ),
        "date": flight.datetime.strftime("%Y-%m-%d %H:%M"),
        "price": flight.price
    }


@app.get("/manage/health")
def health():
    return {"status": "OK"}


@app.get("/internal/flights")
def get_flights(
    page: int = Query(default=0, ge=0),
    size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    total_elements = db.query(Flight).count()

    flights = (
        db.query(Flight)
        .order_by(Flight.id)
        .offset(page * size)
        .limit(size)
        .all()
    )

    return {
        "page": page + 1,
        "pageSize": len(flights),
        "totalElements": total_elements,
        "items": [
            format_flight(flight)
            for flight in flights
        ]
    }


@app.get("/internal/flights/{flight_number}")
def get_flight(
    flight_number: str,
    db: Session = Depends(get_db)
):
    flight = (
        db.query(Flight)
        .filter(Flight.flight_number == flight_number)
        .first()
    )

    if flight is None:
        raise HTTPException(
            status_code=404,
            detail="Flight not found"
        )

    return format_flight(flight)
