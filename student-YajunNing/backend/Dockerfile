FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY agentic_loop.py .
COPY database_client.py .
COPY flights.py .
COPY llm_client.py .
COPY prompt_loader.py .
COPY prompts ./prompts

EXPOSE 5000

CMD ["python", "app.py"]
