#!/bin/bash
# Ollama entrypoint script - starts server and pulls model
set -e

# Start Ollama server in background
ollama serve &

# Wait for server to be ready
echo "Waiting for Ollama server to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama server is ready"
        break
    fi
    sleep 1
done

# Pull the model if specified
MODEL=${OLLAMA_MODEL:-llama3}
echo "Pulling model: $MODEL"
ollama pull "$MODEL" || echo "Warning: Failed to pull model $MODEL, it may already exist"

# Keep container running
wait
