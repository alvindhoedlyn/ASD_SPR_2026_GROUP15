FROM ollama/ollama:latest
ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_KEEP_ALIVE=-1
EXPOSE 11434
ENTRYPOINT ["/bin/sh", "-c", "ollama serve & until ollama list >/dev/null 2>&1; do sleep 1; done; for m in qwen2.5:0.5b llama3.1:8b; do for i in 1 2 3 4 5; do ollama pull $m && break; sleep 10; done; done; wait"]
