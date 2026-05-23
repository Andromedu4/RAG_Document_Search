# Deployment

## Recommended Review Deployment

Use Docker Compose:

```bash
cp .env.example .env
docker compose up --build
```

Set in `.env`:

```env
SECRET_KEY=<long random secret>
AI_PROVIDER=openai
OPENAI_API_KEY=<key>
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/ai_blog
```

## Production Checklist

- Use managed PostgreSQL with pgvector enabled.
- Run `alembic upgrade head` as a release step, not inside multiple app replicas.
- Keep `DATABASE_URL` pointed at PostgreSQL; Render URLs are normalized to the installed `psycopg` driver automatically.
- Use a strong `SECRET_KEY`.
- Keep `OPENAI_API_KEY` in a secret manager.
- Set `AI_PROVIDER=openai` only in trusted environments.
- Public demo users are isolated by the `rag_workspace_id` cookie.
- Configure OpenAI project budgets and usage alerts.
- Persist `UPLOAD_DIR` or replace it with object storage. The app only needs the local file until background indexing finishes, but original uploads are not durable on ephemeral disks.
- Put the app behind TLS and a reverse proxy.
- Add rate limits for auth, uploads, search, and RAG ask.
- Add malware scanning before accepting untrusted files.

## Scaling Notes

The demo uses FastAPI background tasks so upload requests return quickly while extraction, chunking, and embedding continue after the response. That is enough for a portfolio deployment with one web instance. The next production step is a separate durable queue:

- `ai_jobs` table for status/retry metadata.
- Redis + RQ, Dramatiq, or Celery worker.
- API writes pending jobs and a worker updates processing status.

Do not add Kubernetes until the app is already deployed and operational with Docker or a platform-as-a-service target.
