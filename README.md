# Nepal Constitution Knowledge Graph (KG)

## Overview
This project constructs a knowledge graph (KG) based on the Nepal Constitution. It captures the hierarchical and relational structure of constitutional articles, clauses, and legal references. The KG can be used for research, legal analysis, and educational purposes.

## Project Structure

```

nepal-constitution-kg/
│
├── data/
│   ├── raw/           # Original raw data sources (PDFs, CSVs, JSON)
│   └── processed/     # Cleaned, structured, and KG-ready data
│
├── docs/              # Documentation and schema diagrams
│
├── outputs/           # Visualizations, exported graphs, tables
│
├── scripts/           # ETL scripts and data preprocessing
│
├── src/
│   └── ingestion/     # KG ingestion and construction scripts
│
├── streamlit/         # Streamlit app for KG exploration
│
└── tests/             # Unit tests for scripts and data pipelines

````

## Features

- **Data Ingestion:** Extracts articles and clauses from raw legal documents.
- **Knowledge Graph Construction:** Builds entities (articles, clauses) and relationships (references, hierarchy).
- **Visualization:** Graph visualization for exploring relationships and dependencies.
- **Streamlit App:** Interactive interface to explore and query the KG.
- **Testing & Validation:** Unit tests to ensure data integrity and reproducibility.

## Tools & Technologies

- Python
- Pandas, NetworkX
- Streamlit (for interactive KG exploration)
- Pytest (for unit testing)
- Graph visualization libraries (e.g., Pyvis, Matplotlib)

## How to Run

1. Clone the repository:

```bash
git clone git@github.com:USERNAME/nepal-constitution-kg.git
cd nepal-constitution-kg
````

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run scripts to preprocess data and build KG:

```bash
python src/ingestion/build_kg.py
```

4. Start the Streamlit app:

```bash
streamlit run streamlit/app.py
```

## Future Work

* Add NLP-based semantic similarity to discover implicit references.
* Integrate with a search engine for legal queries.
* Deploy the Streamlit app as a web service for broader access.

