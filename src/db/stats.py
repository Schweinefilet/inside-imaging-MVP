"""Aggregate statistics for dashboard and analytics views."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict

from src.db.connection import _format_timestamp, fetch_all, fetch_one
from src.db.patients import _format_tags_display, _parse_age, normalize_study_name


def _gender_bucket(label: str) -> str:
    u = (label or "").strip().upper()
    if u.startswith("M"): return "male"
    if u.startswith("F"): return "female"
    return "other"


def _age_bucket(age: int) -> str:
    if age < 18: return "0-17"
    if age <= 30: return "18-30"
    if age <= 50: return "31-50"
    if age <= 65: return "51-65"
    return "66+"


def get_stats() -> Dict[str, Any]:
    """Return aggregate statistics over the patients table."""
    total = (fetch_one("SELECT COUNT(*) FROM patients") or (0,))[0]
    last_30 = (fetch_one(
        "SELECT COUNT(*) FROM patients WHERE created_at >= datetime('now', '-30 day')"
    ) or (0,))[0]
    avg_words = (fetch_one(
        "SELECT AVG(word_count) FROM patients WHERE word_count > 0"
    ) or (0,))[0] or 0

    gender = {"male": 0, "female": 0, "other": 0}
    for sex, count in fetch_all("SELECT sex, COUNT(*) FROM patients GROUP BY sex"):
        gender[_gender_bucket(sex)] += count

    ranges = {"0-17": 0, "18-30": 0, "31-50": 0, "51-65": 0, "66+": 0}
    for bucket, count in fetch_all(
        """
        SELECT
            CASE
                WHEN CAST(age AS INTEGER) BETWEEN 1 AND 17  THEN '0-17'
                WHEN CAST(age AS INTEGER) BETWEEN 18 AND 30 THEN '18-30'
                WHEN CAST(age AS INTEGER) BETWEEN 31 AND 50 THEN '31-50'
                WHEN CAST(age AS INTEGER) BETWEEN 51 AND 65 THEN '51-65'
                WHEN CAST(age AS INTEGER) > 65              THEN '66+'
            END AS bucket,
            COUNT(*) AS cnt
        FROM patients
        WHERE age IS NOT NULL AND age != '' AND CAST(age AS INTEGER) > 0
        GROUP BY bucket
        """
    ):
        if bucket:
            ranges[bucket] += count

    language_mix = [
        {"label": row[0], "count": row[1]}
        for row in fetch_all(
            "SELECT language, COUNT(*) AS c FROM patients"
            " WHERE ifnull(language, '') != ''"
            " GROUP BY language ORDER BY c DESC"
        )
    ]

    study_counts: Counter = Counter()
    for raw, count in fetch_all(
        "SELECT study, COUNT(*) FROM patients"
        " WHERE ifnull(study, '') != ''"
        " GROUP BY study ORDER BY 2 DESC"
    ):
        study_counts[normalize_study_name(raw)] += count
    study_mix = [{"label": k, "count": v} for k, v in study_counts.most_common()]

    disease_counter: Counter = Counter()
    for (raw,) in fetch_all(
        "SELECT disease_tags FROM patients WHERE ifnull(disease_tags, '') != ''"
    ):
        disease_counter.update(t.strip() for t in raw.split(",") if t.strip())
    disease_mix = [{"label": k, "count": v} for k, v in disease_counter.most_common()]

    recent = [
        {
            "id": row[0],
            "study": row[1] or "Unknown",
            "language": row[2] or "",
            "created_at": _format_timestamp(row[3]),
            "disease_tags": _format_tags_display(
                [t for t in (row[4] or "").split(",") if t]
            ),
        }
        for row in fetch_all(
            "SELECT id, study, language, created_at, disease_tags FROM patients"
            " ORDER BY datetime(created_at) DESC LIMIT 6"
        )
    ]

    series_raw = {
        row[0]: row[1]
        for row in fetch_all(
            "SELECT DATE(created_at), COUNT(*) FROM patients"
            " WHERE created_at >= datetime('now', '-30 day')"
            " GROUP BY DATE(created_at) ORDER BY 1 ASC"
        )
    }
    time_series = []
    for i in range(30):
        d = datetime.now() - timedelta(days=29 - i)
        time_series.append({
            "label": d.strftime("%m/%d"),
            "value": series_raw.get(d.strftime("%Y-%m-%d"), 0),
        })

    return {
        "summary": {
            "total_reports": total,
            "last_30_days": last_30,
            "average_word_count": int(round(avg_words)) if avg_words else 0,
            "languages_tracked": len(language_mix),
        },
        "gender": gender,
        "age_ranges": ranges,
        "languages": language_mix,
        "studies": study_mix,
        "diseases": disease_mix,
        "recent": recent,
        "time_series": time_series,
    }
