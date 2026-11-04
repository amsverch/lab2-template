
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.bonus.database import Base, engine, get_db
from services.bonus.models import Privilege, PrivilegeHistory


app = FastAPI(
    title="Bonus Service",
    description="Service for managing user bonus accounts",
    version="1.0.0"
)


class BonusOperationRequest(BaseModel):
    ticket_uid: UUID = Field(alias="ticketUid")
    balance_diff: int = Field(alias="balanceDiff", gt=0)
    operation_type: Literal[
        "FILL_IN_BALANCE",
        "DEBIT_THE_ACCOUNT"
    ] = Field(alias="operationType")

    model_config = {"populate_by_name": True}


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/manage/health")
def health():
    return {"status": "OK"}


def get_or_create_privilege(username: str, db: Session):
    privilege = (
        db.query(Privilege)
        .filter(Privilege.username == username)
        .first()
    )

    if privilege is None:
        privilege = Privilege(
            username=username,
            status="BRONZE",
            balance=0
        )
        db.add(privilege)
        db.commit()
        db.refresh(privilege)

    return privilege


@app.get("/internal/privilege/{username}")
def get_privilege(
    username: str,
    db: Session = Depends(get_db)
):
    privilege = get_or_create_privilege(username, db)

    history = (
        db.query(PrivilegeHistory)
        .filter(PrivilegeHistory.privilege_id == privilege.id)
        .order_by(PrivilegeHistory.datetime.desc())
        .all()
    )

    return {
        "balance": privilege.balance,
        "status": privilege.status,
        "history": [
            {
                "date": item.datetime.isoformat() + "Z",
                "ticketUid": str(item.ticket_uid),
                "balanceDiff": item.balance_diff,
                "operationType": item.operation_type
            }
            for item in history
        ]
    }


@app.post("/internal/privilege/{username}/operations")
def perform_operation(
    username: str,
    request: BonusOperationRequest,
    db: Session = Depends(get_db)
):
    privilege = get_or_create_privilege(username, db)

    # Проверяем, не выполнялась ли уже такая операция по билету.
    existing = (
        db.query(PrivilegeHistory)
        .filter(
            PrivilegeHistory.privilege_id == privilege.id,
            PrivilegeHistory.ticket_uid == request.ticket_uid,
            PrivilegeHistory.operation_type == request.operation_type
        )
        .first()
    )

    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="This operation has already been performed"
        )

    amount = request.balance_diff

    if request.operation_type == "FILL_IN_BALANCE":
        privilege.balance += amount

    else:
        if privilege.balance < amount:
            raise HTTPException(
                status_code=400,
                detail="Not enough bonus points"
            )

        privilege.balance -= amount

    history_record = PrivilegeHistory(
        privilege_id=privilege.id,
        ticket_uid=request.ticket_uid,
        datetime=datetime.utcnow(),
        balance_diff=amount,
        operation_type=request.operation_type
    )

    db.add(history_record)
    db.commit()
    db.refresh(privilege)

    return {
        "balance": privilege.balance,
        "status": privilege.status
    }


@app.post("/internal/privilege/{username}/revert/{ticket_uid}")
def revert_operation(
    username: str,
    ticket_uid: UUID,
    db: Session = Depends(get_db)
):
    privilege = (
        db.query(Privilege)
        .filter(Privilege.username == username)
        .first()
    )

    if privilege is None:
        raise HTTPException(
            status_code=404,
            detail="Privilege account not found"
        )

    original = (
        db.query(PrivilegeHistory)
        .filter(
            PrivilegeHistory.privilege_id == privilege.id,
            PrivilegeHistory.ticket_uid == ticket_uid
        )
        .first()
    )

    if original is None:
        raise HTTPException(
            status_code=404,
            detail="Original operation not found"
        )

    if original.operation_type == "FILL_IN_BALANCE":
        reverse_type = "DEBIT_THE_ACCOUNT"
        reverse_amount = min(original.balance_diff, privilege.balance)
        privilege.balance -= reverse_amount

    else:
        reverse_type = "FILL_IN_BALANCE"
        reverse_amount = original.balance_diff
        privilege.balance += reverse_amount

    # Не допускаем повторной отмены одной операции.
    already_reverted = (
        db.query(PrivilegeHistory)
        .filter(
            PrivilegeHistory.privilege_id == privilege.id,
            PrivilegeHistory.ticket_uid == ticket_uid,
            PrivilegeHistory.operation_type == reverse_type
        )
        .first()
    )

    if already_reverted is not None:
        raise HTTPException(
            status_code=409,
            detail="This operation has already been reverted"
        )

    history_record = PrivilegeHistory(
        privilege_id=privilege.id,
        ticket_uid=ticket_uid,
        datetime=datetime.utcnow(),
        balance_diff=reverse_amount,
        operation_type=reverse_type
    )

    db.add(history_record)
    db.commit()
    db.refresh(privilege)

    return {
        "balance": privilege.balance,
        "status": privilege.status
    }
