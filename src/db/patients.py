"""Patient analytics records: encounters, disease tagging, study normalization."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.db.connection import _format_timestamp, execute, fetch_all, fetch_one


def truncate_name(name: str) -> str:
    """Return a truncated version of a patient's name.

    First letter of each word + ***. Empty input → empty string.
    """
    if not name:
        return ""
    parts = name.split()
    return " ".join(p[0] + "***" for p in parts)


def _parse_age(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    parts = re.findall(r"\d+", str(raw))
    if not parts:
        return None
    try:
        return int(parts[0])
    except Exception:
        return None


_DISEASE_KEYWORDS = {
    "oncology": ["tumor", "mass", "neoplasm", "malignan", "carcinoma", "metastasis", "lymphadenopathy", "nodule"],
    "fracture": ["fracture", "break", "compression fracture", "dislocation", "subluxation"],
    "infection": ["infection", "abscess", "pneumonia", "sepsis", "consolidation", "infiltrate", "bronchitis"],
    "inflammation": ["inflamm", "itis", "colitis", "hepatitis", "diverticulitis", "pancreatitis"],
    "hemorrhage": ["hemorrhage", "bleed", "hematoma", "contusion"],
    "degeneration": ["degeneration", "arthrosis", "arthritis", "sclerosis", "spondylosis", "fibrosis", "stenosis", "osteophytes"],
    "vascular": ["aneurysm", "stenosis", "thrombus", "embol", "infarct", "ischemia", "calcification"],
    "lung_disease": ["copd", "emphysema", "bronchiectasis", "bullae", "bulla", "effusion", "pneumothorax", "air pocket"],
    "normal": ["normal", "unremarkable", "no acute", "negative", "clear", "intact"],
}


def detect_disease_tags(text: str) -> List[str]:
    low = (text or "").lower()
    tags = []
    for label, keywords in _DISEASE_KEYWORDS.items():
        if any(keyword in low for keyword in keywords):
            tags.append(label)
    if "normal" in tags and len(tags) > 1:
        tags.remove("normal")
    if not tags:
        return ["general"]
    return sorted(set(tags))


def _format_tags_display(tags: List[str]) -> List[str]:
    return [t.replace("_", " ").strip().title() for t in tags if t]


def normalize_study_name(study: str) -> str:
    """Normalize raw study names into professional medical language for stats."""
    if not study or study.lower() == "unknown":
        return "Unknown"
    low = study.lower()

    modality = ""
    if "mri" in low:
        modality = "MRI"
    elif "ct" in low or "computed tomography" in low:
        modality = "CT"
    elif "x-ray" in low or "plain film" in low or "radiograph" in low:
        modality = "X-ray"
    elif "ultrasound" in low or "usg" in low:
        modality = "Ultrasound"
    elif "mammogram" in low:
        modality = "Mammogram"
    elif "pet" in low:
        modality = "PET/CT"
    if not modality:
        return study.title()

    contrast = ""
    if "without contrast" in low or "non-contrast" in low or "without dye" in low:
        contrast = " (non-contrast)"
    elif "with contrast" in low or "with iv contrast" in low or "with dye" in low:
        contrast = " (with contrast)"

    region = ""
    has_abdomen = "abdomen" in low or "abdominal" in low or "tummy" in low or "belly" in low
    has_pelvis = "pelvis" in low or "pelvic" in low
    if "head" in low or "brain" in low:
        region = "Head"
    elif "chest" in low and (has_abdomen or has_pelvis):
        region = "Chest/Abdomen/Pelvis"
    elif "chest" in low:
        region = "Chest"
    elif has_abdomen and has_pelvis:
        region = "Abdomen/Pelvis"
    elif has_abdomen:
        region = "Abdomen"
    elif has_pelvis:
        region = "Pelvis"
    elif "kub" in low:
        region = "KUB"
    elif "urogram" in low:
        region = "Urogram"
    elif "spine" in low:
        if "cervical" in low:
            region = "Cervical Spine"
        elif "thoracic" in low:
            region = "Thoracic Spine"
        elif "lumbar" in low or "lumbosacral" in low:
            region = "Lumbar Spine"
        else:
            region = "Spine"
    elif "foot" in low:
        region = "Foot"
    elif "knee" in low:
        region = "Knee"
    elif "shoulder" in low:
        region = "Shoulder"

    if region:
        return f"{modality} {region}{contrast}"
    return f"{modality}{contrast}"


def add_patient_record(data: Dict[str, Any]) -> int:
    """Insert a patient encounter record and return its new primary key."""
    tags = data.get("disease_tags", [])
    if isinstance(tags, (list, tuple)):
        disease_str = ",".join(sorted({t.strip().lower() for t in tags if t}))
    else:
        disease_str = str(tags or "")
    try:
        word_count = int(data.get("word_count", 0) or 0)
    except Exception:
        word_count = 0
    return execute(
        """
        INSERT INTO patients (
            truncated_name, age, sex, date, hospital, study,
            reason, technique, findings, conclusion, concern, language,
            word_count, disease_tags, username, context
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            truncate_name(data.get("name", "")),
            data.get("age", ""), data.get("sex", ""), data.get("date", ""),
            data.get("hospital", ""), data.get("study", ""),
            data.get("reason", ""), data.get("technique", ""),
            data.get("findings", ""), data.get("conclusion", ""),
            data.get("concern", ""), data.get("language", ""),
            word_count, disease_str,
            data.get("username", ""), data.get("context", ""),
        ),
    )


def store_report_event(patient: Dict[str, Any], structured: Dict[str, Any],
                       report_stats: Dict[str, Any], language: str,
                       username: str = "", context: str = "") -> int:
    """Persist a summarized encounter for analytics without storing PHI."""
    text_blob = " ".join(filter(None, [
        structured.get("findings"),
        structured.get("conclusion"),
        structured.get("concern"),
    ]))
    disease_tags = detect_disease_tags(text_blob)
    record = {
        "name": patient.get("name", ""), "age": patient.get("age", ""),
        "sex": patient.get("sex", ""), "date": patient.get("date", ""),
        "hospital": patient.get("hospital", ""),
        "study": normalize_study_name(patient.get("study", "")),
        "reason": structured.get("reason", ""),
        "technique": structured.get("technique", ""),
        "findings": structured.get("findings", ""),
        "conclusion": structured.get("conclusion", ""),
        "concern": structured.get("concern", ""),
        "language": language,
        "word_count": report_stats.get("words", 0),
        "disease_tags": disease_tags,
        "username": username, "context": context,
    }
    return add_patient_record(record)


def _split_tags(raw: Optional[str]) -> List[str]:
    return [t for t in (raw or "").split(",") if t]


def get_report_brief(report_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        "SELECT id, study, language, created_at, disease_tags FROM patients WHERE id = ?",
        (report_id,),
    )
    if not row:
        return None
    return {
        "id": row[0],
        "study": row[1] or "Unknown",
        "language": row[2] or "",
        "created_at": _format_timestamp(row[3]),
        "disease_tags": _format_tags_display(_split_tags(row[4])),
    }


def get_report_detail(report_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_one(
        """
        SELECT id, truncated_name, age, sex, date, hospital, study,
               reason, technique, findings, conclusion, concern,
               language, word_count, disease_tags, created_at
        FROM patients WHERE id = ?
        """,
        (report_id,),
    )
    if not row:
        return None
    patient = {
        "hospital": row[5] or "", "study": row[6] or "Unknown",
        "name": row[1] or "", "sex": row[3] or "",
        "age": row[2] or "", "date": row[4] or "", "history": "",
    }
    structured = {
        "reason": row[7] or "", "technique": row[8] or "",
        "findings": row[9] or "", "conclusion": row[10] or "",
        "concern": row[11] or "", "word_count": row[13] or 0,
        "comparison": "", "oral_contrast": "",
    }
    return {
        "id": row[0],
        "patient": patient,
        "structured": structured,
        "language": row[12] or "",
        "word_count": row[13] or 0,
        "disease_tags": _format_tags_display(_split_tags(row[14])),
        "created_at": _format_timestamp(row[15]),
    }


def get_user_reports(username: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Recent reports for a specific user."""
    rows = fetch_all(
        """
        SELECT id, study, language, created_at, disease_tags, truncated_name
        FROM patients
        WHERE username = ?
        ORDER BY datetime(created_at) DESC
        LIMIT ?
        """,
        (username, limit),
    )
    return [
        {
            "id": r[0],
            "study": r[1] or "Unknown Study",
            "language": r[2] or "English",
            "created_at": _format_timestamp(r[3]),
            "disease_tags": _format_tags_display(_split_tags(r[4])),
            "patient_name": r[5] or "Patient",
        }
        for r in rows
    ]
