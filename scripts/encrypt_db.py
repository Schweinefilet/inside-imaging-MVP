"""One-time migration: encrypt an existing plain SQLite database with SQLCipher.

Usage:
    DB_ENCRYPTION_KEY=<your-64-char-hex-key> python scripts/encrypt_db.py

Requires:
    pip install sqlcipher3
    brew install sqlcipher          # macOS
    # or: apt install libsqlcipher-dev  (Debian/Ubuntu)

The script:
  1. Backs up the original database to data/patient_data.db.backup
  2. Creates an encrypted copy at data/patient_data.db.enc
  3. Replaces data/patient_data.db with the encrypted copy

After running, set DB_ENCRYPTION_KEY in your .env and restart the app.
"""

import os
import shutil
import sys
from pathlib import Path

DB_PATH = Path("data/patient_data.db")
BACKUP_PATH = Path("data/patient_data.db.backup")
ENCRYPTED_PATH = Path("data/patient_data.db.enc")


def main():
    key = os.environ.get("DB_ENCRYPTION_KEY", "").strip()
    if not key:
        sys.exit("ERROR: DB_ENCRYPTION_KEY environment variable is not set.")
    if len(key) != 64 or not all(c in "0123456789abcdefABCDEF" for c in key):
        sys.exit("ERROR: DB_ENCRYPTION_KEY must be a 64-character hex string (32 bytes).\n"
                 "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"")

    if not DB_PATH.exists():
        sys.exit(f"ERROR: Database not found at {DB_PATH}")

    try:
        import sqlcipher3
    except ImportError:
        sys.exit(
            "ERROR: sqlcipher3 is not installed.\n"
            "Install with: pip install sqlcipher3\n"
            "  macOS: brew install sqlcipher\n"
            "  Ubuntu/Debian: apt install libsqlcipher-dev"
        )

    # Verify this is a plain (unencrypted) SQLite file
    import sqlite3
    try:
        test_conn = sqlite3.connect(str(DB_PATH))
        test_conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        test_conn.close()
    except Exception as exc:
        sys.exit(
            f"ERROR: Could not open {DB_PATH} as plain SQLite: {exc}\n"
            "The database may already be encrypted, or it may be corrupted."
        )

    print(f"Backing up {DB_PATH} → {BACKUP_PATH}")
    shutil.copy2(str(DB_PATH), str(BACKUP_PATH))

    print("Encrypting database...")
    conn = sqlcipher3.connect(str(DB_PATH))
    try:
        conn.execute(f"ATTACH DATABASE '{ENCRYPTED_PATH}' AS encrypted KEY \"x'{key}'\"")
        conn.execute("SELECT sqlcipher_export('encrypted')")
        conn.execute("DETACH DATABASE encrypted")
    finally:
        conn.close()

    print(f"Replacing {DB_PATH} with encrypted copy")
    ENCRYPTED_PATH.replace(DB_PATH)

    print("\nDone. Your database is now encrypted.")
    print(f"Original backed up at: {BACKUP_PATH}")
    print("\nNext steps:")
    print(f"  1. Add DB_ENCRYPTION_KEY={key} to your .env")
    print("  2. Restart the app")
    print("  3. Verify it starts correctly, then delete the backup if desired")


if __name__ == "__main__":
    main()
