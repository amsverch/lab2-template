from uuid import UUID

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field


app = FastAPI(title="Flight Booking API Gateway")


# Адреса внутренних сервисов.
# При локальном запуске они работают на localhost.

import os
FLIGHT_SERVICE_URL = os.getenv(
    "FLIGHT_SERVICE_URL",
    "http://localhost:8060"
)

TICKET_SERVICE_URL = os.getenv(
    "TICKET_SERVICE_URL",
    "http://localhost:8070"
)

BONUS_SERVICE_URL = os.getenv(
    "BONUS_SERVICE_URL",
    "http://localhost:8050"
)



def service_request(method: str, url: str, **kwargs):
    """
    Отправляет HTTP-запрос внутреннему сервису.
    Если сервис недоступен или вернул ошибку, преобразует её
    в понятную ошибку Gateway.
    """
    try:
        response = httpx.request(method, url, timeout=10.0, **kwargs)
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Внутренний сервис временно недоступен"
        )

    if response.status_code >= 400:
        try:
            error_data = response.json()
            message = error_data.get("detail", error_data.get("message", "Ошибка внутреннего сервиса"))
        except ValueError:
            message = "Ошибка внутреннего сервиса"

        raise HTTPException(
            status_code=response.status_code,
            detail=message
        )

    return response


def get_flight(flight_number: str):
    """Получает информацию о рейсе из Flight Service."""
    response = service_request(
        "GET",
        f"{FLIGHT_SERVICE_URL}/internal/flights/{flight_number}"
    )
    return response.json()


def get_privilege(username: str):
    """Получает бонусный счёт пользователя из Bonus Service."""
    response = service_request(
        "GET",
        f"{BONUS_SERVICE_URL}/internal/privilege/{username}"
    )
    return response.json()


def get_ticket(ticket_uid: str, username: str):
    """Получает билет и проверяет, что он принадлежит пользователю."""
    response = service_request(
        "GET",
        f"{TICKET_SERVICE_URL}/internal/ticket/{ticket_uid}",
        params={"username": username}
    )
    return response.json()


def enrich_ticket(ticket: dict):
    """
    Добавляет к билету данные о рейсе.
    Ticket Service хранит номер рейса, а Flight Service —
    аэропорты и дату вылета.
    """
    flight = get_flight(ticket["flightNumber"])

    return {
        "ticketUid": ticket["ticketUid"],
        "flightNumber": ticket["flightNumber"],
        "fromAirport": flight["fromAirport"],
        "toAirport": flight["toAirport"],
        "date": flight["date"],
        "price": ticket["price"],
        "status": ticket["status"]
    }


class TicketPurchaseRequest(BaseModel):
    flight_number: str = Field(alias="flightNumber", min_length=1, max_length=20)
    price: int = Field(gt=0)
    paid_from_balance: bool = Field(alias="paidFromBalance")

    model_config = {"populate_by_name": True}


@app.get("/manage/health")
def health():
    return {"status": "OK"}


@app.get("/api/v1/flights")
def list_flights(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100)
):
    """
    Возвращает список рейсов.
    Внешняя нумерация страниц начинается с 1.
    Внутренний Flight Service принимает номер страницы с 0.
    """
    response = service_request(
        "GET",
        f"{FLIGHT_SERVICE_URL}/internal/flights",
        params={"page": page - 1, "size": size}
    )
    return response.json()


@app.get("/api/v1/privilege")
def privilege_info(
    x_user_name: str = Header(..., alias="X-User-Name")
):
    return get_privilege(x_user_name)


@app.get("/api/v1/tickets")
def list_tickets(
    x_user_name: str = Header(..., alias="X-User-Name")
):
    response = service_request(
        "GET",
        f"{TICKET_SERVICE_URL}/internal/tickets/{x_user_name}"
    )

    tickets = response.json()
    return [enrich_ticket(ticket) for ticket in tickets]


@app.get("/api/v1/tickets/{ticket_uid}")
def ticket_info(
    ticket_uid: UUID,
    x_user_name: str = Header(..., alias="X-User-Name")
):
    ticket = get_ticket(str(ticket_uid), x_user_name)
    return enrich_ticket(ticket)


@app.get("/api/v1/me")
def user_info(
    x_user_name: str = Header(..., alias="X-User-Name")
):
    tickets_response = service_request(
        "GET",
        f"{TICKET_SERVICE_URL}/internal/tickets/{x_user_name}"
    )

    tickets = [
        enrich_ticket(ticket)
        for ticket in tickets_response.json()
    ]

    privilege = get_privilege(x_user_name)

    return {
        "tickets": tickets,
        "privilege": {
            "balance": privilege["balance"],
            "status": privilege["status"]
        }
    }


@app.post("/api/v1/tickets")
def buy_ticket(
    request: TicketPurchaseRequest,
    x_user_name: str = Header(..., alias="X-User-Name")
):
    # 1. Проверяем, что рейс существует.
    flight = get_flight(request.flight_number)

    # 2. Получаем бонусный счёт пользователя.
    privilege = get_privilege(x_user_name)

    # 3. Рассчитываем оплату.
    if request.paid_from_balance:
        paid_by_bonuses = min(privilege["balance"], request.price)
    else:
        paid_by_bonuses = 0

    paid_by_money = request.price - paid_by_bonuses

    # 4. Создаём билет в Ticket Service.
    ticket_response = service_request(
        "POST",
        f"{TICKET_SERVICE_URL}/internal/tickets",
        json={
            "username": x_user_name,
            "flightNumber": request.flight_number,
            "price": request.price
        }
    )

    ticket = ticket_response.json()
    ticket_uid = ticket["ticketUid"]

    # 5. Записываем бонусную операцию.
    # Если билет оплачен деньгами, начисляем 10% его стоимости.
    # Если использован бонусный баланс, списываем использованные бонусы.
    try:
        if paid_by_bonuses > 0:
            service_request(
                "POST",
                f"{BONUS_SERVICE_URL}/internal/privilege/{x_user_name}/operations",
                json={
                    "ticketUid": ticket_uid,
                    "balanceDiff": paid_by_bonuses,
                    "operationType": "DEBIT_THE_ACCOUNT"
                }
            )
        elif not request.paid_from_balance:
            bonus_reward = request.price // 10

            if bonus_reward > 0:
                service_request(
                    "POST",
                    f"{BONUS_SERVICE_URL}/internal/privilege/{x_user_name}/operations",
                    json={
                        "ticketUid": ticket_uid,
                        "balanceDiff": bonus_reward,
                        "operationType": "FILL_IN_BALANCE"
                    }
                )

    except HTTPException:
        # Если бонусная операция не удалась, отменяем созданный билет.
        try:
            service_request(
                "DELETE",
                f"{TICKET_SERVICE_URL}/internal/ticket/{ticket_uid}",
                params={"username": x_user_name}
            )
        finally:
            raise

    # 6. Получаем обновлённый бонусный счёт.
    updated_privilege = get_privilege(x_user_name)

    return {
        "ticketUid": ticket_uid,
        "flightNumber": ticket["flightNumber"],
        "fromAirport": flight["fromAirport"],
        "toAirport": flight["toAirport"],
        "date": flight["date"],
        "status": ticket["status"],
        "price": ticket["price"],
        "paidByMoney": paid_by_money,
        "paidByBonuses": paid_by_bonuses,
        "privilege": {
            "balance": updated_privilege["balance"],
            "status": updated_privilege["status"]
        }
    }


@app.delete("/api/v1/tickets/{ticket_uid}", status_code=204)
def cancel_ticket(
    ticket_uid: UUID,
    x_user_name: str = Header(..., alias="X-User-Name")
):
    # 1. Проверяем существование билета и его владельца.
    ticket = get_ticket(str(ticket_uid), x_user_name)

    if ticket["status"] == "CANCELED":
        raise HTTPException(
            status_code=409,
            detail="Билет уже отменён"
        )

    # 2. Проверяем историю бонусных операций по этому билету.
    privilege = get_privilege(x_user_name)

    ticket_operations = [
        operation
        for operation in privilege.get("history", [])
        if operation["ticketUid"] == str(ticket_uid)
    ]

    # 3. Отменяем бонусную операцию, если она была.
    if ticket_operations:
        service_request(
            "POST",
            f"{BONUS_SERVICE_URL}/internal/privilege/{x_user_name}/revert/{ticket_uid}"
        )

    # 4. Меняем статус билета на CANCELED.
    service_request(
        "DELETE",
        f"{TICKET_SERVICE_URL}/internal/ticket/{ticket_uid}",
        params={"username": x_user_name}
    )

    return None