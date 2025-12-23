# nepal_consti_bot.py
import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
import torch
from sentence_transformers import SentenceTransformer, util
import pickle
import numpy as np

load_dotenv()

# Neo4j connection
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USER")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

# Load embeddings and article data
@st.cache_resource
def load_data():
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Load article data (number, title, text, part)
    import pandas as pd
    articles_df = pd.read_json("data/processed/day4_articles_dense.json", lines=True)
    
    # Load pre-computed embeddings (from Day 4)
    embeddings = torch.load("data/processed/article_features.pt")
    
    return embedder, articles_df, embeddings

embedder, articles_df, embeddings = load_data()

# Function to get full context from graph
def get_context(article_numbers):
    query = """
    MATCH (a:Article)
    WHERE a.number IN $numbers
    OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(cl:Clause)
    
    // Collect all referenced Schedules (via Clause or direct)
    OPTIONAL MATCH (cl)-[:REFERENCES_SCHEDULE]->(s:Schedule)
    OPTIONAL MATCH (a)-[:REFERENCES_SCHEDULE]->(s2:Schedule)
    
    // Deduplicate schedules properly
    WITH a, collect(DISTINCT cl) AS clauses, 
         [sched IN collect(DISTINCT s) + collect(DISTINCT s2) WHERE sched IS NOT NULL] AS all_schedules
    WITH a, clauses, apoc.coll.toSet(all_schedules) AS unique_schedules
    
    RETURN a.number AS num, 
           a.title AS title,
           [c IN clauses | c.clause_id + ": " + c.text] AS clauses,
           [s IN unique_schedules | s.title] AS schedule_titles
    ORDER BY a.number
    """
    with driver.session() as session:
        result = session.run(query, numbers=article_numbers)
        context = ""
        for record in result:
            context += f"**Article {record['num']}: {record['title']}**\n\n"

            if record['clauses']:
                context += "**Clauses:**\n" + "\n".join(record['clauses']) + "\n\n"

            if record['schedule_titles']:
                context += "**Related Schedules:**\n" + "\n".join(record['schedule_titles']) + "\n\n"
            else:
                context += "**Related Schedules:** None\n\n"

            context += "---\n\n"
        return context or "No context found."

# Main query function
@st.cache_data(show_spinner="Searching the Constitution...")
def answer_question(question):
    # Embed the question
    question_emb = embedder.encode(question, convert_to_tensor=True)
    
    # Cosine similarity search
    cos_scores = util.cos_sim(question_emb, embeddings)[0]
    top_k = min(5, len(cos_scores))
    top_indices = torch.topk(cos_scores, k=top_k).indices.cpu().tolist()
    
    # Get article numbers
    top_articles = articles_df.iloc[top_indices]['number'].tolist()
    
    # Get full context
    context = get_context(top_articles)
    
    # Simple answer generation (you can plug in Grok or any LLM here)
    answer = f"**Answer based on the Constitution of Nepal 2015:**\n\n"
    answer += "Here are the most relevant provisions:\n\n"
    answer += context
    
    answer += f"\n**Top matched Articles**: {', '.join([str(n) for n in top_articles])}"
    
    return answer

# Streamlit UI
st.set_page_config(page_title="NepalConstiBot", page_icon="🇳🇵", layout="wide")

st.title("Nepal Constitution Bot")
st.subheader("Ask any question about the Constitution of Nepal 2015")


question = st.text_input("Your question:", placeholder="e.g., What are the fundamental rights to equality?")

if question:
    with st.spinner("Searching the Constitution..."):
        answer = answer_question(question)
    st.markdown(answer)

driver.close()