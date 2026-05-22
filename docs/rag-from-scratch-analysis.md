# `rag-from-scratch-main` Analysis

The folder is a RAG curriculum, not a web application. The project uses it as a methodology source.

## Notebooks 1-4: Base RAG

Core concepts:

- load documents
- split text recursively
- embed chunks
- store vectors
- retrieve by similarity
- answer from retrieved context

Implemented in this project.

## Notebooks 5-9: Query Transformations

Concepts:

- Multi Query
- RAG-Fusion
- Reciprocal Rank Fusion
- Decomposition
- Step-back prompting
- HyDE

These should become selectable retrieval strategies.

## Notebooks 10-11: Routing and Query Construction

Concepts:

- structured route selection
- semantic routing
- converting natural language into metadata filters

These should become a query analyzer before retrieval.

## Notebooks 12-14: Advanced Indexing

Concepts:

- multi-representation indexing
- summary vectors
- parent document retriever
- RAPTOR-style hierarchy
- ColBERT-style retrieval

These should become advanced indexing modes after the base app is stable.

## Notebooks 15-18: Retrieval Quality

Concepts:

- reranking
- contextual compression
- CRAG
- Self-RAG
- long-context risk

These should become the evaluation and quality-control layer.
