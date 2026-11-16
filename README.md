# Nepal Constitution Knowledge Graph

Turns the Constitution of Nepal (2015) into a Neo4j knowledge graph, uses graph machine learning to predict missing cross-references, and serves a Streamlit app that answers questions by combining embedding search with graph lookups.

## What it does

1. **PDF parsing** (`src/ingestion/pdf_parser_plumber.py`): extracts parts, articles, clauses and schedules from the constitution PDF with pdfplumber and saves them as JSON.
2. **Graph construction** (`src/ingestion/neo4j_loader.py`): loads them into Neo4j as `Constitution`, `Part`, `Article`, `Clause` and `Schedule` nodes, linked by relationships such as `HAS_PART`, `HAS_ARTICLE`, `HAS_CLAUSE`, `REFERENCES_SCHEDULE` and `RELATES_TO_ARTICLE`.
3. **Link prediction, classical** (`scripts/link_prediction.py`): logistic regression on graph features (common neighbours, Jaccard, preferential attachment, node types) to suggest likely missing references, with a 60/20/20 train/validation/test split scored by ROC-AUC.
4. **Link prediction, GNN** (`scripts/gnn_day4.py`): GCN vs. GraphSAGE encoders on sentence-transformer embeddings of each article (`all-MiniLM-L6-v2`), compared on test ROC-AUC, F1 and inference time.
5. **Q&A app** (`streamlit/nepal_consti_bot.py`): embeds the question, finds the closest articles by cosine similarity, then queries Neo4j to pull in each article's clauses and linked schedules and shows them as the answer.

## Project structure

```
nepal-constitution-kg/
├── data/processed/        # parsed JSON, NetworkX graphs (.gpickle), embeddings, trained GNN weights
├── scripts/
│   ├── run_ingestion.py   # PDF → JSON → Neo4j
│   ├── export_graph.py    # Neo4j → NetworkX graph
│   ├── export_day4.py     # denser graph + article table for the GNN
│   ├── link_prediction.py # classical link prediction
│   └── gnn_day4.py        # GCN vs. GraphSAGE
├── src/ingestion/         # pdfplumber parser and Neo4j loader
├── streamlit/             # Q&A app
└── requirements.txt
```

## Tools

Python, pdfplumber, Neo4j, NetworkX, scikit-learn, PyTorch, PyTorch Geometric, sentence-transformers, Streamlit.

## How to run

```bash
git clone https://github.com/sansritaulak/nepal-constitution-kg.git
cd nepal-constitution-kg
pip install -r requirements.txt
```

Create a `.env` file with your Neo4j connection (the app uses APOC, so enable that plugin):

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password
```

Put the constitution PDF in `data/raw/` (PDFs are not committed), then:

```bash
python scripts/run_ingestion.py      # parse the PDF and load Neo4j
python scripts/link_prediction.py    # classical link prediction
python scripts/gnn_day4.py           # GCN vs. GraphSAGE
streamlit run streamlit/nepal_consti_bot.py
```

The processed graphs and embeddings in `data/processed/` are committed, so the link-prediction scripts can run without re-parsing the PDF.

## Future work

- Generate written answers with an LLM on top of the retrieved articles (graph RAG).
- Use semantic similarity to discover implicit references between articles.
- Deploy the app as a web service.
