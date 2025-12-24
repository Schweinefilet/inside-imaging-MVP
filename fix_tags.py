
import sqlite3
import sys
import os

# Ensure we can import from src
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.db import get_connection, detect_disease_tags

def fix_all_tags():
    conn = get_connection()
    cur = conn.cursor()
    
    print("Fetching all reports...")
    # Fetch technique as well to infer study type
    cur.execute("SELECT id, findings, conclusion, concern, disease_tags, study, technique FROM patients")
    rows = cur.fetchall()
    
    updated_count = 0
    study_updated_count = 0
    
    for row in rows:
        pid = row[0]
        # Reconstruct blob for tagging
        blob = " ".join(filter(None, [row[1], row[2], row[3]]))
        
        # Calculate new tags
        new_tags_list = detect_disease_tags(blob)
        new_tags_str = ",".join(new_tags_list)
        
        old_tags_str = row[4] or ""
        
        # Update tags if changed
        if set(new_tags_list) != set(filter(None, old_tags_str.split(","))):
            cur.execute("UPDATE patients SET disease_tags = ? WHERE id = ?", (new_tags_str, pid))
            updated_count += 1

        # Infer study type if unknown
        current_study = (row[5] or "").strip()
        technique = (row[6] or "").strip()
        
        if (not current_study or current_study.lower() == "unknown") and technique:
            new_study = ""
            tech_lower = technique.lower()
            
            # Try to extract the full procedure description from the technique field
            # Look for common patterns like "X-ray (plain film) of..." or "CT scan of..."
            import re
            
            # Pattern 1: "X-ray (details) of body part" - extract up to first period or newline
            m = re.match(r"(X-ray[^.;\n]+)", technique, re.IGNORECASE)
            if m:
                new_study = m.group(1).strip()
            elif "ct " in tech_lower or "computed tomography" in tech_lower:
                m = re.match(r"(CT[^.;\n]+|Computed tomography[^.;\n]+)", technique, re.IGNORECASE)
                if m:
                    new_study = m.group(1).strip()
                else:
                    new_study = "Computed Tomography (CT scan)"
            elif "mri " in tech_lower or "magnetic resonance" in tech_lower:
                m = re.match(r"(MRI[^.;\n]+|Magnetic resonance[^.;\n]+)", technique, re.IGNORECASE)
                if m:
                    new_study = m.group(1).strip()
                else:
                    new_study = "MRI"
            elif "ultrasound" in tech_lower or "sonogram" in tech_lower:
                m = re.match(r"(Ultrasound[^.;\n]+|Sonogram[^.;\n]+)", technique, re.IGNORECASE)
                if m:
                    new_study = m.group(1).strip()
                else:
                    new_study = "Ultrasound"
                
            if new_study:
                print(f"Updating Study ID {pid}: '{current_study}' -> '{new_study}'")
                cur.execute("UPDATE patients SET study = ? WHERE id = ?", (new_study, pid))
                study_updated_count += 1
            
    conn.commit()
    conn.close()
    print(f"Done. Updated {updated_count} tags and {study_updated_count} studies.")

if __name__ == "__main__":
    fix_all_tags()
