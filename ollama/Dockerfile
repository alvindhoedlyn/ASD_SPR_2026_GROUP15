FROM ollama/ollama:latest
ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_KEEP_ALIVE=-1
RUN ollama serve & \
    pid=$!; \
    until ollama list >/dev/null 2>&1; do sleep 1; done; \
    ollama pull qwen2.5:0.5b; \
    ollama pull llama3.1:8b; \
    kill $pid
EXPOSE 11434