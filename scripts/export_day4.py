from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import networkx as nx
import pickle
import pandas as pd

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

G = nx.Graph()
article_data = []

with driver.session() as session:
    print("1. Exporting Articles...")
    result = session.run("""
        MATCH (p:Part)-[:HAS_ARTICLE]->(a:Article)
        RETURN a.number AS num, a.title AS title, a.full_text AS text, p.number AS part_num
    """)
    for record in result:
        num = record["num"]
        G.add_node(num, title=record["title"], text=record["text"], part=record["part_num"])
        article_data.append({"number": num, "title": record["title"], "text": record["text"], "part": record["part_num"]})

    print("2. Adding Structural Edges (Direct References)...")
    result = session.run("""
        MATCH (a1:Article)-[:REFERENCES|RELATES_TO_ARTICLE]->(a2:Article)
        RETURN a1.number AS u, a2.number AS v
    """)
    for record in result:
        G.add_edge(record["u"], record["v"], type="direct_ref")

    print("3. Adding Hierarchy Edges (Same Part / Shared Schedule)...")
    # Link articles in the same Part (Strong thematic density)
    result = session.run("""
        MATCH (a1:Article)<-[:HAS_ARTICLE]-(p:Part)-[:HAS_ARTICLE]->(a2:Article)
        WHERE a1.number < a2.number
        RETURN a1.number AS u, a2.number AS v
    """)
    for record in result:
        G.add_edge(record["u"], record["v"], type="shared_part")

    # Shared Schedule references
    result = session.run("""
        MATCH (a1:Article)-[:REFERENCES_SCHEDULE]->(s:Schedule)<-[:REFERENCES_SCHEDULE]-(a2:Article)
        WHERE a1.number < a2.number
        RETURN a1.number AS u, a2.number AS v
    """)
    for record in result:
        G.add_edge(record["u"], record["v"], type="shared_schedule")

    print("4. Adding Semantic Keyword Edges (Title Overlap)...")
    # Fix: Changed len(word) to size(word)
    result = session.run("""
        MATCH (a1:Article), (a2:Article)
        WHERE a1.number < a2.number
        AND any(word IN split(toLower(a1.title), ' ') 
            WHERE size(word) > 5 AND toLower(a2.title) CONTAINS word)
        RETURN a1.number AS u, a2.number AS v
    """)
    for record in result:
        G.add_edge(record["u"], record["v"], type="title_keyword_overlap")

print(f"Final Dense Graph for Day 4: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Saving code remains the same...

# Save graph and article data
graph_path = "data/processed/day4_graph_dense.gpickle"
with open(graph_path, "wb") as f:
    pickle.dump(G, f)

articles_path = "data/processed/day4_articles_dense.json"
pd.DataFrame(article_data).to_json(articles_path, orient="records", lines=True)

print(f"Graph saved to {graph_path}")
print(f"Article data saved to {articles_path}")

driver.close()