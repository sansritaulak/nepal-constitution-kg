# Nepal Constitution 2015 Knowledge Graph + RAG

A 5-day project to build a knowledge graph from the Constitution of Nepal (2015) and enable RAG queries.

## Day 1: Schema & Ingestion
- Parse PDF
- Extract Parts, Articles, Clauses
- Load into Neo4j

## Setup
1. pip install -r requirements.txt
2. Set up Neo4j and add credentials to .env
3. Run: python -m scripts.run_ingestion