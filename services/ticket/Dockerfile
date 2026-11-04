FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/ticket ./services/ticket

EXPOSE 8070

CMD ["uvicorn", "services.ticket.main:app", "--host", "0.0.0.0", "--port", "8070"]