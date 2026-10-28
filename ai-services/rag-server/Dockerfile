FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt requests
COPY . .
ENV PORT=5100
EXPOSE 5100
CMD ["python", "rag_http_server.py"]