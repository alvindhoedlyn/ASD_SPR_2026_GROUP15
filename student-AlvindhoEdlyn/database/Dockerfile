FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask

COPY init_db.py .

EXPOSE 6001

CMD ["python", "init_db.py"]