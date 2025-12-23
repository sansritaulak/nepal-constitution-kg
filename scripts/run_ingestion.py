# scripts/run_ingestion.py
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ingestion.pdf_parser_plumber import parse_constitution
from src.ingestion.neo4j_loader import Neo4jLoader

PDF_PATH = "data/raw/Constitution-of-Nepal_2072_Eng_www.moljpa.gov_.npDate-72_11_16.pdf"
PROCESSED_DIR = "data/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Separate JSON paths
parts_json = os.path.join(PROCESSED_DIR, "parts.json")
articles_json = os.path.join(PROCESSED_DIR, "articles.json")
clauses_json = os.path.join(PROCESSED_DIR, "clauses.json")
schedules_json = os.path.join(PROCESSED_DIR, "schedules.json")

print("Parsing Constitution with pdfplumber...")
data = parse_constitution(PDF_PATH)

# Prepare flat clauses list for saving
flat_clauses = []
for article in data["articles"]:
    for clause in article["clauses"]:
        clause_copy = clause.copy()
        clause_copy["article_number"] = article["number"]
        clause_copy["article_title"] = article["title"]
        clause_copy["part_number"] = article["part_number"]
        clause_copy["part_title"] = article["part_title"]
        flat_clauses.append(clause_copy)

# Save separate JSON files
print("\nSaving entities to separate JSON files...")

with open(parts_json, "w", encoding="utf-8") as f:
    json.dump(data["parts"], f, indent=2, ensure_ascii=False)
print(f"✅ Parts saved to {parts_json} ({len(data['parts'])} parts)")

with open(articles_json, "w", encoding="utf-8") as f:
    json.dump(data["articles"], f, indent=2, ensure_ascii=False)
print(f"✅ Articles saved to {articles_json} ({len(data['articles'])} articles)")

with open(clauses_json, "w", encoding="utf-8") as f:
    json.dump(flat_clauses, f, indent=2, ensure_ascii=False)
print(f"✅ Clauses saved to {clauses_json} ({len(flat_clauses)} clauses)")

with open(schedules_json, "w", encoding="utf-8") as f:
    json.dump(data["schedules"], f, indent=2, ensure_ascii=False)
print(f"✅ Schedules saved to {schedules_json} ({len(data['schedules'])} schedules)")

print("\nLoading into Neo4j...")
loader = Neo4jLoader()
loader.load_plumber_data(data)
loader.close()
