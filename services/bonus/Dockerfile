FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/bonus ./services/bonus

EXPOSE 8050

CMD ["uvicorn", "services.bonus.main:app", "--host", "0.0.0.0", "--port", "8050"]