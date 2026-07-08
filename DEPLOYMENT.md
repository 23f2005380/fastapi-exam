# Deployment Guide

## GitHub Repository
https://github.com/23f2005380/fastapi-exam

## Bundle Service (Covers Q1, Q2, Q3, Q5, Q6, Q8, Q9, Q10)
Deploy on **Render.com** from the `bundle/` directory:

1. Go to https://dashboard.render.com/ → New Web Service
2. Connect your GitHub repo `23f2005380/fastapi-exam`
3. Settings:
   - **Root Directory**: `bundle`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Endpoint URLs (once deployed to `<BASE_URL>`):

| Question | Endpoint | URL |
|----------|----------|-----|
| Q1 | GET /stats?values=... | `<BASE_URL>/stats?values=1,2,3` |
| Q2 | POST /verify | `<BASE_URL>/verify` |
| Q3 | GET /effective-config?set=... | `<BASE_URL>/effective-config?set=port=9000` |
| Q5 | POST /analytics | `<BASE_URL>/analytics` |
| Q6 | GET /work, /metrics, /healthz, /logs/tail | `<BASE_URL>/work?n=100` |
| Q8 | POST /extract | `<BASE_URL>/extract` |
| Q9 | POST /orders + GET /orders | `<BASE_URL>/orders` |
| Q10 | GET /ping | `<BASE_URL>/ping` |

## Q4: Docker Compose + Redis
Run locally:
```bash
cd q4_compose
docker-compose up -d
```
Expose via cloudflared:
```bash
cloudflared tunnel --url http://localhost:8000
```

## Q7: Local LLM via Ollama
Run (after Ollama installs):
```bash
set OLLAMA_ORIGINS=*
ollama serve
# In another terminal:
ollama pull llama3.2
cloudflared tunnel --url http://localhost:11434
```
Tunnel URL becomes: `https://<id>.trycloudflare.com/v1/chat/completions`
