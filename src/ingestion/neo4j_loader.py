# src/ingestion/neo4j_loader.py
from neo4j import GraphDatabase # type: ignore
from dotenv import load_dotenv # type: ignore
import os
import re

load_dotenv()

class Neo4jLoader:
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def load_plumber_data(self, data: dict):
        with self.driver.session() as session:
            # Root Constitution
            session.run("MERGE (c:Constitution {name: 'Constitution of Nepal 2015'})")

            # Parts
            for part in data["parts"]:
                session.run("""
                    MATCH (c:Constitution)
                    MERGE (p:Part {number: $number})
                    SET p.title = $title
                    MERGE (c)-[:HAS_PART]->(p)
                """, number=part["part_number"], title=part["part_title"])

            # Schedules (before articles so nodes exist)
            for sched in data["schedules"]:
                session.run("""
                    MATCH (c:Constitution)
                    MERGE (s:Schedule {number: $number})
                    SET s.title = $title,
                        s.relating_to = $relating_to,
                        s.full_text = $full_text
                    MERGE (c)-[:HAS_SCHEDULE]->(s)
                """, number=sched["number"],
                     title=sched["title"],
                     relating_to=sched.get("relating_to", ""),
                     full_text=sched["full_text"])

            # Articles & Clauses
            for article in data["articles"]:
                session.run("""
                    MATCH (p:Part {number: $part_num})
                    MERGE (a:Article {number: $art_num})
                    SET a.title = $title, a.full_text = $full_text
                    MERGE (p)-[:HAS_ARTICLE]->(a)
                """, part_num=article["part_number"], art_num=article["number"],
                     title=article["title"], full_text=article["full_text"])

                for clause in article["clauses"]:
                    # SKIP: If clause '1' is just the article title/full text repeated
                    # Adjust the threshold (e.g., 80% length) if necessary
                    is_header_dup = (clause["clause_id"] == "1" and 
                                    (article["title"].lower() in clause["text"].lower() or 
                                    len(clause["text"]) > len(article["full_text"]) * 0.8))
                    
                    if is_header_dup:
                        continue

                    session.run("""
                        MATCH (a:Article {number: $art_num})
                        MERGE (cl:Clause {clause_id: $clause_id, article_num: $art_num})
                        SET cl.text = $text
                        MERGE (a)-[:HAS_CLAUSE]->(cl)
                    """, art_num=article["number"], clause_id=clause["clause_id"], text=clause["text"])

                    # Clause → Schedule references (single source of truth)
                    for sched_num in clause["schedule_refs"]:
                        session.run("""
                            MATCH (cl:Clause {clause_id: $clause_id})
                            MATCH (s:Schedule {number: $sched_num})
                            MERGE (cl)-[:REFERENCES_SCHEDULE]->(s)
                        """, clause_id=clause["clause_id"], sched_num=sched_num)

            # Schedule → Article from relating_to (bidirectional)
            for sched in data["schedules"]:
                if sched.get("relating_to"):
                    article_refs = re.findall(r"Article\s*(\d+)", sched["relating_to"], re.IGNORECASE)
                    for art_num_str in set(article_refs):
                        art_num = int(art_num_str)
                        session.run("""
                            MATCH (s:Schedule {number: $sched_num})
                            MATCH (a:Article {number: $art_num})
                            MERGE (s)-[:RELATES_TO_ARTICLE]->(a)
                            MERGE (a)-[:REFERENCES_SCHEDULE]->(s)
                        """, sched_num=sched["number"], art_num=art_num)

            # === ENRICHMENT NODES ===
            print("Adding enrichment nodes...")

            # 1. Fundamental Rights (Articles 16–46 in Part 3)
            session.run("""
                MATCH (p:Part {number: 3})-[:HAS_ARTICLE]->(a:Article)
                WHERE a.number >= 16 AND a.number <= 46
                MERGE (fr:FundamentalRight {name: a.title})
                ON CREATE SET fr.main_article = a.number
                MERGE (a)-[:DEFINES_RIGHT]->(fr)
                MERGE (fr)-[:IN_PART]->(p)
            """)

            # 2. Directive Principles (Automated from Article 50 clauses - 4 nodes)
            session.run("""
                // Main Directive Principles node
                MATCH (a50:Article {number: 50})
                MERGE (dp:DirectivePrinciple {name: "Directive Principles of the State"})
                ON CREATE SET 
                    dp.description = "Non-justiciable guiding principles defined in Article 50",
                    dp.article_number = 50
                MERGE (a50)-[:HAS_DIRECTIVE_PRINCIPLE]->(dp)

                // Pass the required variables to the next part of the query
                WITH a50, dp

                // Collect the 4 clauses and set as properties on the single node
                MATCH (a50)-[:HAS_CLAUSE]->(cl:Clause)
                WHERE cl.clause_id IN ["50(1)", "50(2)", "50(3)", "50(4)"]
                WITH dp, cl
                ORDER BY cl.clause_id
                WITH dp, collect(cl.text) AS clause_texts
                SET dp.clause1_text = clause_texts[0],
                    dp.clause2_text = clause_texts[1],
                    dp.clause3_text = clause_texts[2],
                    dp.clause4_text = clause_texts[3]
            """)

            # 3. Institutions (17 major ones + auto-linked)
            institutions = [
                "President", "Vice-President", "Federal Executive", "Prime Minister",
                "Council of Ministers", "Federal Parliament", "Federal Legislature",
                "Judiciary", "Supreme Court", "High Court", "Attorney General", 
                "Election Commission", "Public Service Commission",
                "National Human Rights Commission", "Commission for the Investigation of Abuse of Authority",
                "Auditor General", "National Natural Resources and Fiscal Commission"
            ]

            for name in institutions:
                session.run("MERGE (i:Institution {name: $name})", name=name)

            # Link Institutions to Articles/Parts by title keyword
            session.run("""
                MATCH (i:Institution)
                MATCH (a:Article)
                WHERE toLower(a.title) CONTAINS toLower(i.name)
                   OR toLower(a.title) CONTAINS toLower(split(i.name, " ")[0])
                MERGE (a)-[:ESTABLISHES]->(i)
            """)

            session.run("""
                MATCH (i:Institution)
                MATCH (p:Part)
                WHERE toLower(p.title) CONTAINS toLower(i.name)
                MERGE (p)-[:ESTABLISHES]->(i)
            """)

            # 4. Amendment (Part 31 + Article 274)
            session.run("""
                MERGE (am:Amendment {name: "Amendment to the Constitution"})
                SET am.description = "Process governed by Part 31 and primarily Article 274"
                WITH am
                MATCH (p:Part {number: 31})
                MERGE (p)-[:DEFINES]->(am)
                WITH am
                MATCH (a:Article {number: 274})
                MERGE (a)-[:GOVERNS]->(am)
            """)

            print("✅ Enrichment complete: FundamentalRight, DirectivePrinciple, Institution, Amendment added")

            # Final summary
            print("Loaded into Neo4j:")
            print(f"  Parts: {len(data['parts'])}")
            print(f"  Articles: {len(data['articles'])}")
            print(f"  Clauses: {sum(len(a['clauses']) for a in data['articles'])}")
            print(f"  Schedules: {len(data['schedules'])}")
            print("  Enrichment: Fundamental Rights, Directive Principles, Institutions, Amendment")

    def close(self):
        self.driver.close()