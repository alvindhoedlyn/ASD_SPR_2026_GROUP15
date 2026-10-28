FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt requests
COPY . .
ENV MCP_HOST=0.0.0.0 MCP_PORT=5200
EXPOSE 5200
CMD ["python", "server.py"]