FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY database/ ./database/

WORKDIR /app/backend

EXPOSE 5001

CMD ["python", "app.py"]
