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
- Persist `UPLOAD_DIR` or replace it with object storage.
- Put the app behind TLS and a reverse proxy.
- Add rate limits for auth, uploads, search, and RAG ask.
- Add malware scanning before accepting untrusted files.

## Scaling Notes

The MVP indexes synchronously after upload. That keeps the implementation easy to review and test. The next production step is to move extraction and embedding into a background queue:

- `ai_jobs` table for status/retry metadata.
- Redis + RQ, Dramatiq, or Celery worker.
- API writes pending jobs and returns processing status.

Do not add Kubernetes until the app is already deployed and operational with Docker or a platform-as-a-service target.
