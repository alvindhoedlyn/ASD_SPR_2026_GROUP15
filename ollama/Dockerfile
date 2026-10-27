FROM ollama/ollama:latest
ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_KEEP_ALIVE=-1
EXPOSE 11434
ENTRYPOINT ["/bin/sh", "-c", "ollama serve & until ollama list >/dev/null 2>&1; do sleep 1; done; for i in 1 2 3 4 5; do ollama pull qwen2.5:0.5b && break; sleep 10; done; wait"]
