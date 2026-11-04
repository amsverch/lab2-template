FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/flight ./services/flight

EXPOSE 8060

CMD ["uvicorn", "services.flight.main:app", "--host", "0.0.0.0", "--port", "8060"]