"""
run_lab.py — UPSC Agent Lab Cockpit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Single entry point for the entire pipeline.

USAGE:
  Mode A (topic name):
    python run_lab.py

  Mode B (NCERT PDF):
    Drop a PDF into data/input_pdfs/ and uncomment its path in PDF_FILES_TO_INGEST below.
    Set PDF_MODE = True.

WHAT IT DOES:
  1. Builds / verifies database schema (Layer 2 & 3 support)
  2. Generates/Retrieves Book Intelligence Plan (Layer 1)
  3. Runs the 3-Layer Quality Engine for each topic/PDF
  4. Prints a full DB summary with quality metrics
  5. Tells you to launch the UI server
"""

import os
import sys

from src.architect import build_schema
from src.ingestor import ingest_topic
from src.database import get_db_connection
from src.book_planner import generate_book_plan, get_book_plan

# Add root folder to pythonpath (fallback for certain environments)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ══════════════════════════════════════════════════════════════════
# ⚙️  CONFIGURE YOUR INGESTION HERE
# ══════════════════════════════════════════════════════════════════

# ── MODE A: Topic strings ──────────────────────────────────────────────────
# Uncomment topics to ingest. Run one at a time first for verification.
# All topics are registered in src/cross_subject_map.py (instant classification).

TOPICS_TO_INGEST = [
    # ── POLITY CORE (start here — most UPSC weight) ───────────────────
    "Parliament of India",  # ← ACTIVE: first test
    # "President of India",
    # "Prime Minister of India",
    # "Cabinet Committees",
    # "Fundamental Rights",
    # "Directive Principles of State Policy",
    # "Preamble of Indian Constitution",
    # "Judicial Review & Judicial Activism",
    # "Election Process & Electoral Reforms",
    # "Federalism & Centre-State Relations",
    # "Federalism & Local Governance",
    # "Indian Constitution & Freedom Struggle Legacy",
    # "Indian Constitution & Governance",
    # ── ECONOMY & FINANCE ─────────────────────────────────────────────
    # "Budget & Fiscal Policy",               # Cross: Polity + Governance
    # "Economic Development & Growth",
    # "Poverty & Inequality",
    # "Agricultural Reforms",                 # Cross: Geography + Polity
    # "Food Security",                        # Cross: Geography + Governance
    # "Infrastructure Development",
    # "Industrial Policy",
    # "Trade & WTO",                          # Cross: IR + Polity
    # "Globalization & Its Impact",           # Cross: IR + Society
    # "Startup Ecosystem & Innovation",       # Cross: Science & Tech
    # "Land Reforms",                         # Cross: History + Polity
    # "Energy Security",                      # Cross: Geography + IR + Environment
    # ── GOVERNANCE & SOCIAL JUSTICE ───────────────────────────────────
    # "Social Justice (SC/ST/OBC)",           # Cross: Polity + History
    # "Women Empowerment",                    # Cross: Polity + Economy
    # "NGOs & Civil Society",
    # "Health Sector in India",               # Cross: Economy + Science
    # "Education System in India",            # Cross: Economy + Governance
    # "Ethics, Integrity & Aptitude",
    # ── ENVIRONMENT & GEOGRAPHY ───────────────────────────────────────
    # "Climate Change",                       # Cross: Geography + Economy + IR
    # "Environment & Agriculture Linkage",    # Cross: Economy + Geography
    # "Water Resource Management",            # Cross: Polity + Economy + Environment
    # "Disaster Management",                  # Cross: Geography + Governance
    # "Urbanization",                         # Cross: Economy + Environment
    # "Population & Demographics",            # Cross: Economy + Governance
    # "Migration (Internal & International)", # Cross: IR + Economy
    # ── SCIENCE & TECHNOLOGY ──────────────────────────────────────────
    # "Science & Technology in Governance",   # Cross: Polity + Governance
    # "Cyber Security",                       # Cross: Security + Polity
    # "Space Technology",                     # Cross: IR + Security
    # "Biotechnology",                        # Cross: Environment + Ethics
    # ── INTERNATIONAL RELATIONS ───────────────────────────────────────
    # "India's Foreign Policy",               # Cross: History + Geography + Economy
    # "Border Issues & Disputes",             # Cross: Geography + Security + History
    # "Regional Organizations (SAARC, ASEAN, SCO)", # Cross: Economy + Geography
    # ── INTERNAL SECURITY ─────────────────────────────────────────────
    # "Internal Security (Terrorism & Naxalism)", # Cross: Geography + Polity
]

# ── MODE B: NCERT PDFs (NCERT as spine + Wikipedia as enricher) ───────────
# Drop PDFs into data/input_pdfs/ first, then uncomment the path below.
PDF_FILES_TO_INGEST = [
    # "data/input_pdfs/ncert_polity_ch22_parliament.pdf",
    # "data/input_pdfs/ncert_polity_ch17_president.pdf",
    # "data/input_pdfs/ncert_polity_ch13_fundamental_rights.pdf",
    # "data/input_pdfs/ncert_economy_ch01_development.pdf",
    # "data/input_pdfs/ncert_geography_ch01_resources.pdf",
]

# ── SHARED CONFIG ──────────────────────────────────────────────────────────
PDF_MODE = False  # Set to True to enable PDF ingestion (Mode B)

# ══════════════════════════════════════════════════════════════════


def print_db_summary():
    """Prints a full summary of what's in the database after ingestion."""
    print()
    print("━" * 55)
    print("📊 DATABASE SUMMARY")
    print("━" * 55)
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM nodes")
    node_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM edges")
    edge_count = cur.fetchone()[0]

    cur.execute("SELECT SUM(word_count) FROM nodes WHERE word_count > 0")
    total_words = cur.fetchone()[0] or 0

    cur.execute("SELECT AVG(quality_score) FROM nodes WHERE quality_score > 0")
    avg_quality = cur.fetchone()[0] or 0

    print(f"  Total Nodes  : {node_count}")
    print(f"  Total Edges  : {edge_count}")
    print(f"  Total Words  : {total_words:,} words of content")
    print(f"  Est. Pages   : ~{total_words // 300} pages (at 300 words/page)")
    print(f"  Avg Quality  : {avg_quality:.1f} / 100 (3-Layer Engine)")

    print()
    print("  Nodes by type:")
    cur.execute(
        "SELECT type, COUNT(*), SUM(word_count) FROM nodes GROUP BY type ORDER BY MIN(level)"
    )
    for row in cur.fetchall():
        ntype, count, words = row
        icon = {"subject": "📚", "module": "📂", "topic": "📄", "subtopic": "🔹"}.get(
            ntype, "⚪"
        )
        words = words or 0
        print(f"    {icon}  {ntype:<12}: {count:>3} nodes | {words:>8,} words")

    print()
    print("  Full Hierarchy (with word counts):")
    cur.execute("""
        SELECT n.label, n.type, n.level, n.word_count, n.source
        FROM nodes n
        ORDER BY n.level, n.id
    """)
    for label, ntype, level, wc, source in cur.fetchall():
        indent = "    " + "  " * (level - 1)
        icon = {"subject": "📚", "module": "📂", "topic": "📄", "subtopic": "🔹"}.get(
            ntype, "⚪"
        )
        wc_str = f"{wc:,} words" if wc and wc > 0 else ""
        src_str = f"[{source}]" if source != "system" else ""
        print(f"{indent}{icon} {label}  {wc_str}  {src_str}")

    print()
    print("  Recent ingestion logs:")
    cur.execute("""
        SELECT topic_name, status, nodes_created, edges_created, created_at
        FROM ingestion_logs
        ORDER BY created_at DESC LIMIT 5
    """)
    for row in cur.fetchall():
        topic, status, nodes, edges, ts = row
        icon = "✅" if status == "success" else "❌"
        print(f"    {icon} {topic}  →  {nodes} nodes, {edges} edges  ({ts})")

    conn.close()


def main():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║      🧪  UPSC AGENT LAB — DEEP CONTENT ENGINE   ║")
    print("╚══════════════════════════════════════════════════╝")

    # ── Step 1: Schema ────────────────────────────────────────────
    print()
    print("STEP 1: Building / Verifying Schema...")
    build_schema()

    # ── Step 1.5: Book Intelligence Plan ─────────────────────────────
    # For each subject being ingested, generate book plan first:
    SUBJECT = "Indian Constitution & Polity"
    MODULES = [
        "Union Legislature",
        "Union Executive",
        "Union Judiciary",
        "State Government",
        "Fundamental Rights & Duties",
        "Directive Principles",
        "Constitutional Amendments",
        "Emergency Provisions",
        "Federalism & Centre-State Relations",
        "Constitutional Bodies",
    ]

    # Check if plan already exists
    existing_plan = get_book_plan(SUBJECT)
    if not existing_plan:
        print(f"\nSTEP 1.5: Generating Book Intelligence Plan for '{SUBJECT}'...")
        generate_book_plan(SUBJECT, MODULES)
        print("   ✅ Book plan created. All subsequent articles will use it.")
    else:
        print(f"\nSTEP 1.5: Book plan already exists for '{SUBJECT}' — skipping.")

    # ── Step 2: Mode A ingestion ──────────────────────────────────
    if TOPICS_TO_INGEST:
        print()
        print(f"STEP 2A: Ingesting {len(TOPICS_TO_INGEST)} topic(s) [Mode A]...")
        for topic in TOPICS_TO_INGEST:
            ingest_topic(topic_name=topic)

    # ── Step 3: Mode B PDF ingestion ──────────────────────────────
    if PDF_MODE and PDF_FILES_TO_INGEST:
        print()
        print(f"STEP 2B: Ingesting {len(PDF_FILES_TO_INGEST)} PDF(s) [Mode B]...")
        for pdf_path in PDF_FILES_TO_INGEST:
            if os.path.exists(pdf_path):
                ingest_topic(pdf_path=pdf_path)
            else:
                print(f"  ⚠️  PDF not found: '{pdf_path}' — skipping")

    # ── Step 4: Summary ───────────────────────────────────────────
    print_db_summary()

    # ── Step 5: Launch instructions ───────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║         ✅  PIPELINE COMPLETE!                   ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║                                                  ║")
    print("║  Launch the UI server:                           ║")
    print("║    uvicorn src.server:app --reload               ║")
    print("║                                                  ║")
    print("║  Then open: http://127.0.0.1:8000                ║")
    print("║                                                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()


if __name__ == "__main__":
    main()
