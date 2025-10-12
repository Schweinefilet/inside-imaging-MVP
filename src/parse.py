"""Utility functions to parse metadata and sections from radiology reports.

This module normalizes text and extracts key pieces of information such as
patient name, age, sex, date, hospital and study from raw report text. It
also provides helpers to extract blocks of text for the reason for the scan,
technique, findings and impression/conclusion sections.

The intent is to keep all of the parsing logic in one place so that the
translation layer can focus on language simplification without worrying
about pulling data out of unstructured reports.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple, Optional

# Regular expression to detect an all-caps line which may be part of a hospital
# header. Most hospital names and department headings are presented like this.
UPPER_LINE = re.compile(r"^[A-Z0-9&@/()'’.,\- ]{12,}$")

def _norm(s: str) -> str:
    """Normalize whitespace and common dash characters in a string.

    Converts different dash types to a simple hyphen, collapses multiple
    spaces, and trims trailing whitespace on each line. Returns the cleaned
    string.
    """
    # Normalize various dash characters to a single hyphen
    s = s.replace('\u2013', '-').replace('\u2014', '-').replace('\u00a0', ' ')
    # Collapse multiple spaces
    s = re.sub(r"[ \t]+", " ", s)
    # Remove spaces before newlines
    s = re.sub(r"\s+\n", "\n", s)
    return s.strip()

def _get_block(text: str, start_keys: Tuple[str, ...]) -> str:
    """Extract the block of text following any of the provided start keys.

    Given a normalized report and one or more section names, locate the first
    occurrence of any key and return the content from just after that key up
    until the next major section (another all caps heading or a double
    newline). If no key is found, return an empty string.
    """
    t = text
    for k in start_keys:
        # Search for the section header (case-insensitive)
        m = re.search(rf"(?is)\b{k}\b\s*[:\-]?\s*(.*)", t)
        if m:
            # Slice the text from this header onward
            rest = t[m.start():]
            # Look for the next all-caps header indicating the next section
            stop = re.search(r"(?m)^(?:IMPRESSION|CONCLUSION|REPORT|RESULTS|DISCUSSION|NOTE|SUMMARY)\b", rest)
            block = rest if not stop else rest[:stop.start()]
            # Remove the header itself
            block = re.sub(rf"(?is)^{k}\s*[:\-]?\s*", "", block).strip()
            return block
    return ""

def parse_metadata(text: str) -> Dict[str, str]:
    """Parse key metadata fields from a radiology report.

    Returns a dictionary containing hospital name, patient name, age, sex,
    date and study type (e.g. "CT ABDOMEN PELVIS") if they can be found.
    Fields that cannot be extracted will be returned as empty strings.
    """
    t = _norm(text)

    # Attempt to identify a hospital header by looking for consecutive
    # uppercase lines near the top of the document.
    lines = t.splitlines()
    head_upper = []
    for line in lines[:10]:
        if UPPER_LINE.match(line.strip()):
            head_upper.append(line.strip())
        elif head_upper:
            break
    hospital = " ".join(head_upper[:2]).strip() or ""

    # Patient name
    name = ""
    m = re.search(r"(?i)\bNAME\b[:\s\-–]*([A-Z][A-Za-z' .\-]+)", t)
    if m:
        name = m.group(1).strip()

    # Patient age
    age = ""
    m = re.search(r"(?i)\bAGE\b[:\s\-–]*([0-9]{1,3})", t)
    if m:
        age = m.group(1).strip()

    # Patient sex (M/F)
    sex = ""
    m = re.search(r"(?i)\bSEX\b[:\s\-–]*([MF]|Male|Female)", t)
    if m:
        v = m.group(1).strip().lower()
        sex = "M" if v.startswith("m") else ("F" if v.startswith("f") else "")

    # Date of study
    date = ""
    m = re.search(
        r"(?i)\bDATE\b[:\s]*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})",
        t,
    )
    if m:
        date = m.group(1).strip()

    # Study type such as CT, MRI etc. (look for an all-caps line beginning with CT/MRI etc.)
    study = ""
    m = re.search(r"(?m)^(CT|MRI|X[- ]?RAY|ULTRASOUND|USG)[^\n]{0,60}$", t)
    if m:
        study = m.group(0).strip()

    return {
        "hospital": hospital,
        "name": name,
        "age": age,
        "sex": sex,
        "date": date,
        "study": study,
    }

def sections_from_text(text: str) -> Dict[str, str]:
    """Extract core sections from a radiology report.

    Returns a dictionary with the keys reason, technique, findings and
    impression. Each value is the content of that section, or an empty
    string if not found. If a "findings" section isn't explicitly found,
    this will attempt to grab everything after the first "FINDINGS"
    heading.
    """
    t = _norm(text)
    reason = _get_block(t, ("CLINICAL INFORMATION", "INDICATION", "HISTORY"))
    technique = _get_block(t, ("TECHNIQUE",))
    findings = _get_block(t, ("FINDINGS", "FINDING"))
    impression = _get_block(t, ("IMPRESSION", "CONCLUSION"))
    if not findings:
        # Fallback: capture after the first FINDINGS heading if present
        m = re.search(r"(?is)\bFINDINGS?\b[:\s\-]*\n?(.*)", t)
        if m:
            findings = m.group(1).strip()
    return {
        "reason": reason.strip(),
        "technique": technique.strip(),
        "findings": findings.strip(),
        "impression": impression.strip(),
    }