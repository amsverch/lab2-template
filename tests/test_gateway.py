
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient

from services.gateway.main import app


client = TestClient(app)


def test_health():
    response = client.get("/manage/health")

    assert response.status_code == 200
    assert response.json() == {"status": "OK"}


def test_list_flights():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "page": 1,
        "pageSize": 10,
        "totalElements": 1,
        "items": [
            {
                "flightNumber": "AFL031",
                "fromAirport": "Санкт-Петербург Пулково",
                "toAirport": "Москва Шереметьево",
                "date": "2021-10-08 20:00",
                "price": 1500
            }
        ]
    }

    with patch(
        "services.gateway.main.service_request",
        return_value=mock_response
    ) as mocked_request:
        response = client.get("/api/v1/flights?page=1&size=10")

    assert response.status_code == 200
    assert response.json()["items"][0]["flightNumber"] == "AFL031"

    mocked_request.assert_called_once_with(
        "GET",
        "http://localhost:8060/internal/flights",
        params={"page": 0, "size": 10}
    )


def test_flights_invalid_page():
    response = client.get("/api/v1/flights?page=0")

    assert response.status_code == 422


def test_flights_invalid_size():
    response = client.get("/api/v1/flights?size=101")

    assert response.status_code == 422
