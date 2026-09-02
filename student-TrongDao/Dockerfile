# Frontend target
FROM nginx:alpine AS frontend

COPY frontend/ /usr/share/nginx/html/

EXPOSE 80


# Backend target
FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install --no-cache-dir \
    -r backend/requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

EXPOSE 5000

CMD ["python", "app.py"]


# Database target
FROM python:3.12-slim AS database

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=5000
ENV DATABASE_PATH=/app/database/data/location_recommender.db

WORKDIR /app

COPY database/requirements.txt ./database/requirements.txt

RUN pip install --no-cache-dir \
    -r database/requirements.txt

COPY database/ ./database/

WORKDIR /app/database

EXPOSE 5000

CMD ["python", "app.py"]