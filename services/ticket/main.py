
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.ticket.database import Base, engine, get_db
from services.ticket.models import Ticket


app = FastAPI(
    title="Ticket Service",
    description="Service for managing flight tickets",
    version="1.0.0"
)


class TicketCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    flight_number: str = Field(
        alias="flightNumber",
        min_length=1,
        max_length=20
    )
    price: int = Field(gt=0)

    model_config = {"populate_by_name": True}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


def format_ticket(ticket: Ticket):
    return {
        "ticketUid": str(ticket.ticket_uid),
        "username": ticket.username,
        "flightNumber": ticket.flight_number,
        "price": ticket.price,
        "status": ticket.status
    }


@app.get("/manage/health")
def health():
    return {"status": "OK"}


@app.post("/internal/tickets", status_code=201)
def create_ticket(
    request: TicketCreateRequest,
    db: Session = Depends(get_db)
):
    ticket = Ticket(
        username=request.username,
        flight_number=request.flight_number,
        price=request.price,
        status="PAID"
    )

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    return format_ticket(ticket)


@app.get("/internal/tickets/{username}")
def get_tickets(
    username: str,
    db: Session = Depends(get_db)
):
    tickets = (
        db.query(Ticket)
        .filter(Ticket.username == username)
        .order_by(Ticket.id)
        .all()
    )

    return [format_ticket(ticket) for ticket in tickets]


@app.get("/internal/ticket/{ticket_uid}")
def get_ticket(
    ticket_uid: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.ticket_uid == ticket_uid,
            Ticket.username == username
        )
        .first()
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    return format_ticket(ticket)


@app.delete("/internal/ticket/{ticket_uid}", status_code=204)
def cancel_ticket(
    ticket_uid: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    ticket = (
        db.query(Ticket)
        .filter(
            Ticket.ticket_uid == ticket_uid,
            Ticket.username == username
        )
        .first()
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found"
        )

    if ticket.status == "CANCELED":
        raise HTTPException(
            status_code=409,
            detail="Ticket is already canceled"
        )

    ticket.status = "CANCELED"
    db.commit()

    return None
