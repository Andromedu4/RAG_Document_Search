# RAG for Document Search

Production-style pet project based on the ideas from `rag-from-scratch-main`.

The app lets anyone upload a document or submit a website URL, indexes it inside the visitor's demo workspace, retrieves relevant chunks for a question, and generates an answer with cited source snippets.

```text
Indexing -> question -> retrieval -> generation -> answer
```

The main goal is to demonstrate practical RAG engineering, not CRUD:

- document upload for PDF, DOCX, TXT, Markdown
- web URL ingestion for HTML and plain text pages
- cookie-based workspace isolation for public demos
- text extraction and recursive chunking
- embeddings with configurable OpenAI embedding model
- pgvector semantic retrieval
- mock AI provider for free local tests
- answer generation through provider interface
- relevant document snippets returned with score/distance
- provider call logs with token/cost/latency metadata
- tests and Docker Compose

## Product Flow

1. Open your private demo workspace at `/`.
2. Upload a file or submit a website URL.
3. The app extracts readable text, chunks it, embeds chunks, and stores vectors.
4. Ask a question.
5. The retriever returns relevant chunks only from your workspace.
6. The generator answers using only retrieved context.
7. The UI shows the answer plus source snippets used in the answer.

Each visitor gets a `rag_workspace_id` cookie. Documents, chunks, semantic search, and RAG answers are scoped to that workspace so public demo users do not see each other's uploads.

## RAG From Scratch Mapping

| Source notebook | Concept | Project implementation |
| --- | --- | --- |
| `rag_from_scratch_1_to_4.ipynb` | indexing, chunking, embeddings, retriever, generation | implemented MVP pipeline |
| `rag_from_scratch_5_to_9.ipynb` | Multi Query, RAG-Fusion, HyDE, Step-back, Decomposition | planned retriever strategies |
| `rag_from_scratch_10_and_11.ipynb` | routing and metadata query construction | planned query analyzer |
| `rag_from_scratch_12_to_14.ipynb` | multi-representation indexing, parent docs, summaries | planned advanced indexing |
| `rag_from_scratch_15_to_18.ipynb` | reranking, CRAG, Self-RAG, long context risks | planned retrieval quality layer |

See [docs/rag-from-scratch-analysis.md](docs/rag-from-scratch-analysis.md).

## Local Setup

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Run without paid API calls:

```bash
AI_PROVIDER=mock DATABASE_URL=sqlite:///./ai_blog.db uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## OpenAI Mode

Create `.env` from `.env.example` and set:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_RAG_MODEL=gpt-5.4-nano
```

## Groq Mode

Groq is supported for answer generation through its OpenAI-compatible Chat Completions API:

```env
AI_PROVIDER=groq
GROQ_API_KEY=...
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile
```

In Groq-only mode, retrieval uses deterministic local embeddings so the app can be tested with only a Groq key. For production-quality semantic retrieval, use a real embedding provider.

## Docker Compose

```bash
docker compose up --build
```

This starts FastAPI and PostgreSQL with pgvector.

## Main Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Public document search workspace |
| `POST` | `/documents/upload` | Upload, extract, chunk, embed, index |
| `POST` | `/documents/url` | Fetch a web page, extract readable text, chunk, embed, index |
| `POST` | `/workspace/clear` | Clear the current visitor workspace |
| `POST` | `/rag/ask` | Retrieve relevant chunks and generate answer |
| `GET` | `/search/semantic?q=...` | Semantic search API |
| `GET` | `/health` | Health check |

Example URL ingestion:

```bash
curl -X POST http://127.0.0.1:8000/documents/url \
  -F "url=https://example.com/article"
```

Example JSON ask:

```bash
curl -X POST http://127.0.0.1:8000/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What does the uploaded document say about refunds?"}'
```

Response includes:

- `answer`
- `citations`
- `relevant_documents`
- `pipeline`

## Testing

```bash
pytest
ruff check .
```

All AI tests use the mock provider by default and do not require paid API calls.

## Cost Awareness

Every provider call is logged in `provider_call_logs` with:

- provider
- operation
- model
- token usage
- estimated cost
- status
- latency
- error message

Pricing assumptions are centralized in [app/services/costs.py](app/services/costs.py).
