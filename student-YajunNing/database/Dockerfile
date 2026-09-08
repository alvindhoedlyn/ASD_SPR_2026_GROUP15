FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY init_db.py .
COPY schema.sql .

RUN mkdir -p /app/data

EXPOSE 6005

CMD ["python", "app.py"]
