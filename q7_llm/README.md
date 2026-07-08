# Q7: Expose Local LLM Through Tunnel

## Setup Instructions

1. Install Ollama from https://ollama.ai
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Start Ollama with CORS enabled:
   ```bash
   OLLAMA_ORIGINS=* ollama serve
   ```
4. In another terminal, expose via Cloudflare Tunnel:
   ```bash
   cloudflared tunnel --url http://localhost:11434
   ```
5. The tunnel gives you a URL like `https://something.trycloudflare.com`
6. Your endpoint URL: `https://something.trycloudflare.com/v1/chat/completions`
7. Model name: `llama3.2`

Submit as JSON:
```json
{"url": "https://<tunnel-url>/v1/chat/completions", "model": "llama3.2"}
```
