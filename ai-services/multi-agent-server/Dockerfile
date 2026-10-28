FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt flask requests
COPY . .
ENV MULTI_AGENT_PORT=5300
EXPOSE 5300
CMD ["python", "app.py"]