"""Parsers for LLM output: strict JSON, salvage of partial JSON, section splits."""

from __future__ import annotations

import re
from typing import Dict, List


def _split_sections(raw: str) -> Dict[str, str]:
    """Split raw model text into our five sections by fixed headings."""
    if not raw:
        return {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    normalized = raw.replace("\r", "")
    parts_rx = re.compile(
        r"(?is)\b(Reason for the scan|Procedure details|Important Findings|CONCLUSION|NOTE OF CONCERN)\s*:\s*\n?"
        r"(.*?)(?=\n\s*(?:Reason for the scan|Procedure details|Important Findings|CONCLUSION|NOTE OF CONCERN)\s*:|\Z)"
    )

    found: Dict[str, str] = {}
    for m in parts_rx.finditer(normalized):
        key = m.group(1).lower()
        body = (m.group(2) or "").strip()
        if key.startswith("reason"):
            found["reason"] = body
        elif key.startswith("procedure"):
            found["technique"] = body
        elif key.startswith("important"):
            found["findings"] = body
        elif key.startswith("conclusion"):
            found["conclusion"] = body
        elif key.startswith("note of concern"):
            found["concern"] = body

    for k in ("reason", "technique", "findings", "conclusion", "concern"):
        found.setdefault(k, "")
    return found


def _salvage_json_like(raw: str) -> Dict[str, object]:
    """Best-effort extraction when JSON is truncated or slightly malformed."""
    out: Dict[str, object] = {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    def grab_string(key: str) -> str:
        m = re.search(rf'"{key}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw, flags=re.S)
        if m:
            return (m.group(1) or "").strip()
        m2 = re.search(rf'"{key}"\s*:\s*"(.*)$', raw, flags=re.S)
        if m2:
            val = (m2.group(1) or "").strip()
            cut = max(val.rfind("."), val.rfind("!"), val.rfind("?"))
            if cut != -1:
                val = val[: cut + 1]
            val = val.rstrip('\'"} ,')
            return val.strip()
        return ""

    def grab_array(key: str) -> List[str]:
        m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', raw, flags=re.S)
        items: List[str] = []
        if m:
            body = m.group(1) or ""
            for s in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', body, flags=re.S):
                s = (s or "").strip()
                if s:
                    items.append(s)
        return items

    reason = grab_string("reason")
    technique = grab_string("technique")
    findings_list = grab_array("findings")
    findings_str = grab_string("findings") if not findings_list else ""
    conclusion = grab_string("conclusion")
    concern = grab_string("concern")

    if reason: out["reason"] = reason
    if technique: out["technique"] = technique
    if findings_list:
        out["findings"] = findings_list
    elif findings_str:
        out["findings"] = findings_str
    if conclusion: out["conclusion"] = conclusion
    if concern: out["concern"] = concern

    return out
