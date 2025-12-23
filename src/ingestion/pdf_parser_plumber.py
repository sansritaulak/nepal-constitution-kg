# src/ingestion/pdf_parser_plumber.py
import pdfplumber # type: ignore
import re
from typing import Dict

PDF_PATH = "data/raw/nepal_constitution_2015_clean.pdf"  # update if different

ORDINAL_MAP = {
    "first": 1, "second": 2, "third": 3, "fourth": 4,
    "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "ninth": 9, "tenth": 10
}

def extract_full_text(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [page.extract_text() for page in pdf.pages if page.extract_text()]
        return "\n".join(pages)

def parse_constitution(pdf_path: str) -> Dict:
    full_text = extract_full_text(pdf_path)

    # Find start of main content (Article 1)
    first_article_match = re.search(r"^\s*1\.", full_text, re.MULTILINE)
    article_body_start = first_article_match.start() if first_article_match else 0

    # Extract Parts
    part_pattern = re.compile(r"^\s*Part\s*-?\s*(\d+)\s*\n\s*(.+)", re.MULTILINE | re.IGNORECASE)
    all_parts = []
    for match in part_pattern.finditer(full_text):
        all_parts.append({
            "part_number": int(match.group(1)),
            "part_title": match.group(2).strip(),
            "start_pos": match.start()
        })

    # Filter valid parts (last before Article 1 + all after)
    pre_parts = [p for p in all_parts if p["start_pos"] < article_body_start]
    post_parts = [p for p in all_parts if p["start_pos"] >= article_body_start]
    valid_parts = (pre_parts[-1:] if pre_parts else []) + post_parts
    valid_parts = sorted(valid_parts, key=lambda x: x["start_pos"])

    def get_part_for_position(pos):
        for part in reversed(valid_parts):
            if part["start_pos"] <= pos:
                return part
        return None

    # Split text at Schedules (after Article 308)
    last_308_match = None
    for m in reversed(list(re.finditer(r"^\s*308\.", full_text, re.MULTILINE))):
        last_308_match = m
        break

    schedule_start = None
    if last_308_match:
        schedule_headers = list(re.finditer(r"^Schedule\s*-?\s*\d+", full_text, re.MULTILINE | re.IGNORECASE))
        for h in schedule_headers:
            if h.start() > last_308_match.end():
                schedule_start = h.start()
                break

    articles_text = full_text[:schedule_start] if schedule_start else full_text
    schedules_text = full_text[schedule_start:] if schedule_start else ""

    # Extract Articles
    article_pattern = re.compile(r"^\s*(\d+)\.\s*(.*?)(?=^\s*\d+\.|\Z)", re.DOTALL | re.MULTILINE)
    articles = []

    for match in article_pattern.finditer(articles_text):
        art_num = int(match.group(1))
        art_content = match.group(2).strip()

        approx_pos = full_text.find(match.group(0))
        part = get_part_for_position(approx_pos)

        # Improved title extraction (split on colon)
        first_line = art_content.split('\n', 1)[0].strip()

        if ':' in first_line:
            art_title = first_line.split(':', 1)[0].strip()
            art_body = art_content[len(first_line.split(':', 1)[0] + ':'):].strip()
        else:
            art_title = first_line
            art_body = art_content[len(first_line):].strip('\n')

        art_body = art_body.lstrip('\n')

        # Extract clauses (unchanged)
        clauses = []
        clause_pattern = re.compile(r"^\s*\((\d+|[a-z]+)\)\s*(.*?)(?=^\s*\([\d|a-z]+\)|\Z)", re.DOTALL | re.MULTILINE)

        clause_matches = list(clause_pattern.finditer("\n" + art_body))
        if clause_matches:
            for c_match in clause_matches:
                clause_id = c_match.group(1)
                clause_text = c_match.group(2).strip()

                sched_refs = set()
                for ref in re.finditer(r"Schedule\s*-?\s*(\d+)", clause_text, re.IGNORECASE):
                    sched_refs.add(int(ref.group(1)))
                for ref in re.finditer(r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)\s+schedule", clause_text, re.IGNORECASE):
                    sched_refs.add(ORDINAL_MAP[ref.group(1).lower()])

                clauses.append({
                    "clause_id": f"{art_num}({clause_id})",
                    "text": clause_text,
                    "schedule_refs": sorted(sched_refs)
                })
        else:
            sched_refs = set()
            for ref in re.finditer(r"Schedule\s*-?\s*(\d+)", art_body, re.IGNORECASE):
                sched_refs.add(int(ref.group(1)))
            for ref in re.finditer(r"(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)\s+schedule", art_body, re.IGNORECASE):
                sched_refs.add(ORDINAL_MAP[ref.group(1).lower()])

            if art_body:
                clauses.append({
                    "clause_id": f"{art_num}(1)",
                    "text": art_body,
                    "schedule_refs": sorted(sched_refs)
                })

        articles.append({
            "number": art_num,
            "title": art_title,
            "full_text": art_body,
            "part_number": part["part_number"] if part else None,
            "part_title": part["part_title"] if part else None,
            "clauses": clauses
        })
    

    # Extract Schedules - Simple generic titles
    schedule_pattern = re.compile(
        r"^Schedule\s*-?\s*(\d+)\s*(.*?)(?=^Schedule\s*-?\s*\d+|\Z)",
        re.DOTALL | re.MULTILINE | re.IGNORECASE
    )

    schedules = []
    for match in schedule_pattern.finditer(schedules_text):
        sched_num = int(match.group(1))
        sched_content = match.group(2).strip()

        lines = [line.strip() for line in sched_content.split('\n') if line.strip()]

        relating_to_lines = []
        body_lines = []

        i = 0
        while i < len(lines) and lines[i].startswith("("):
            relating_to_lines.append(lines[i])
            i += 1

        body_lines = lines[i:]

        relating_to = " ".join(relating_to_lines).strip("() ").strip()
        full_text = "\n".join(body_lines).strip()

        schedules.append({
            "number": sched_num,
            "title": f"Schedule {sched_num}",
            "relating_to": relating_to,
            "full_text": full_text  # contains real title + list
        })

    # Final summary
    print(f"Extracted {len(valid_parts)} Parts")
    print(f"Extracted {len(articles)} Articles")
    total_clauses = sum(len(a["clauses"]) for a in articles)
    print(f"Extracted {total_clauses} Clauses")
    print(f"Extracted {len(schedules)} Schedules")

    return {
        "parts": valid_parts,
        "articles": articles,
        "schedules": schedules
    }