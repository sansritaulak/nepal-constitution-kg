from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import networkx as nx
import pickle

load_dotenv()

URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def export_graph():
    G = nx.Graph() 

    with driver.session() as session:
        print("Fetching nodes with readable labels...")
        node_query = """
        MATCH (n)
        WHERE n:Article OR n:Part OR n:Schedule OR n:Clause OR 
              n:DirectivePrinciple OR n:Institution OR n:FundamentalRight
        RETURN elementId(n) AS eid, 
               labels(n)[0] AS label, 
               coalesce(n.number, n.clause_id, n.name) AS identifier,
               coalesce(n.title, n.name, n.clause_id) AS title
        """
        nodes = session.run(node_query)
        for record in nodes:
            # Create a readable ID like "Article:50" or "Schedule:1"
            # This ensures uniqueness across different types
            readable_id = f"{record['label']}:{record['identifier']}"
            
            G.add_node(
                readable_id, 
                eid=record["eid"], # Keep the real DB ID as an attribute
                label=record["label"],
                title=record["title"] # Specifically set 'title' for your prediction script
            )

        print("Fetching relationships...")
        rel_query = """
        MATCH (n)-[r]->(m)
        WHERE elementId(n) IN $eids AND elementId(m) IN $eids
        RETURN elementId(n) AS source_eid, elementId(m) AS target_eid, type(r) AS rel_type
        """
        # Map elementIds back to our readable IDs
        eid_to_readable = {data['eid']: node_id for node_id, data in G.nodes(data=True)}
        eids = list(eid_to_readable.keys())
        
        relationships = session.run(rel_query, eids=eids)
        for record in relationships:
            source = eid_to_readable.get(record["source_eid"])
            target = eid_to_readable.get(record["target_eid"])
            if source and target:
                G.add_edge(source, target, rel_type=record["rel_type"])

    print(f"✅ Exported: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    save_path = "data/processed/constitution_graph.gpickle"
    with open(save_path, "wb") as f:
        pickle.dump(G, f)
    print(f"Graph saved to {save_path}")

if __name__ == "__main__":
    try:
        export_graph()
    finally:
        driver.close()