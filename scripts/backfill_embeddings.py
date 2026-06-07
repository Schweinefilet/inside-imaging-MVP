"""Backfill embeddings for approved/implemented feedback records.

Run from the project root:
    python scripts/backfill_embeddings.py

Requires INSIDEIMAGING_ALLOW_LLM=1 and OPENAI_API_KEY to be set.
Safe to run repeatedly — skips records that already have an embedding.
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path regardless of where the script is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)

from src.db.connection import init_db
from src.db.embeddings import embed_approved_feedback

if __name__ == "__main__":
    init_db()
    print("Scanning for approved/implemented feedback records without embeddings...")
    count = embed_approved_feedback()
    if count == 0:
        print("Nothing to embed (all eligible records already have embeddings, or LLM is disabled).")
    else:
        print(f"Embedded {count} record(s) successfully.")
