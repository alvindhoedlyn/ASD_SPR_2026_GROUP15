FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY schema.sql .

EXPOSE 6000

CMD ["python", "app.py"]
