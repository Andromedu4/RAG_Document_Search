# Architecture

## Product

`RAG for Document Search` is a public document-question-answering platform.
For demo safety, each visitor gets a cookie-backed workspace. Uploads, URL sources, chunks, semantic search, and RAG answers are scoped to that workspace.

The core user path is:

```text
upload document
  -> or fetch website URL
  -> queue background processing
  -> extract text
  -> recursive chunking
  -> embeddings
  -> vector index
  -> question
  -> semantic retrieval
  -> context construction
  -> generation
  -> answer + relevant documents
```

## Components

```text
Browser UI
  |
Workspace cookie
  |
FastAPI routes
  |
RAG services
  |
SQLAlchemy models
  |
PostgreSQL + pgvector
```

Important modules:

- `app/services/document_extraction.py` extracts PDF/DOCX/TXT/MD text.
- `app/services/web_extraction.py` validates public URLs, fetches HTML/TXT pages, and extracts readable text.
- `app/services/public_ingestion.py` saves sources quickly, tracks processing status, and runs background indexing.
- `app/services/chunking.py` implements recursive chunking.
- `app/services/indexing.py` stores chunks and embeddings.
- `app/services/search.py` retrieves relevant chunks.
- `app/services/rag.py` builds context and generates an answer.
- `app/services/workspaces.py` creates, clears, and scopes visitor workspaces.
- `app/services/ai_provider.py` keeps OpenAI/mock providers behind one interface.
- `app/services/ai_logging.py` logs cost, tokens, latency, and errors.

Providers:

- `mock`: local deterministic embeddings and test answer generation.
- `openai`: OpenAI Embeddings API plus Responses API.
- `groq`: Groq Chat Completions for answer generation with local deterministic embeddings for Groq-only testing.

## Data Model

- `workspaces`: anonymous visitor workspaces identified by a cookie-safe public id.
- `documents`: uploaded file or URL metadata, original source path/URL, extracted text, and workspace id.
- `post_chunks`: retrievable indexed chunks with vector embeddings and workspace id.
- `provider_call_logs`: provider operation, model, tokens, cost, status, latency.
- `rag_runs`: question, answer, retrieved chunk ids, citations, and workspace id.
- `prompt_templates` and `prompt_runs`: prompt versioning and prompt execution history.

The older `users` and `posts` tables remain for compatibility, but the main RAG workflow is public and does not require login.

## Based on `rag-from-scratch-main`

Current implementation covers the first notebook group:

- indexing
- splitting
- embeddings
- similarity retrieval
- generation from retrieved context

The planned extension path follows the later notebooks:

- Multi Query
- RAG-Fusion with Reciprocal Rank Fusion
- HyDE
- Step-back prompting
- decomposition
- routing
- metadata filters
- multi-representation indexing
- reranking and retrieval grading
