# Implementation Plan

## Current MVP

The MVP implements the base RAG pipeline from `rag_from_scratch_1_to_4.ipynb` as a web app:

```text
Indexing -> question -> retrieval -> generation -> answer
```

Completed:

- public document upload
- public website URL ingestion
- PDF/DOCX/TXT/MD extraction
- HTML/plain-text web page extraction
- cookie-based workspace isolation for public demos
- recursive chunking
- OpenAI-compatible embeddings provider
- mock provider for tests
- pgvector-compatible vector storage
- semantic retriever
- answer generation from retrieved context
- relevant documents in UI/API output
- provider call logs
- tests and Docker Compose

## Next Milestones from `rag-from-scratch-main`

### 1. Query Transformations

From `rag_from_scratch_5_to_9.ipynb`:

- Multi Query retriever
- RAG-Fusion retriever
- Reciprocal Rank Fusion scores
- Decomposition
- Step-back prompting
- HyDE

Each strategy should be selectable in the UI and returned in the trace.

### 2. Routing and Query Construction

From `rag_from_scratch_10_and_11.ipynb`:

- logical router
- semantic router
- metadata filter construction

Example output:

```json
{
  "content_search": "refund policy",
  "source_type": "document",
  "content_type": "application/pdf"
}
```

### 3. Advanced Indexing

From `rag_from_scratch_12_to_14.ipynb`:

- child chunks
- parent document retrieval
- summary embeddings
- retrieve summaries and expand to original documents

### 4. Retrieval Quality

From `rag_from_scratch_15_to_18.ipynb`:

- reranking
- contextual compression
- retrieval confidence grading
- CRAG-inspired retry
- Self-RAG-inspired groundedness checks
- long-context warning

### 5. Evaluation

Add scripts:

```bash
python scripts/run_retrieval_eval.py --strategy similarity
python scripts/compare_retrievers.py --a similarity --b rag_fusion
python scripts/run_answer_eval.py
```

Metrics:

- hit@k
- MRR
- recall@k
- citation rate
- unknown-answer accuracy
- cost per question
- latency
