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

def _simplify_study_name(study: str) -> str:
    """Simplify verbose study descriptions to concise format.
    
    Examples:
        "Multiplanar multisequential MRI scans of the lumbar spine were obtained"
        -> "MRI of lumbar spine"
        
        "CT (special x-ray) of your tummy and pelvis with contrast"
        -> "CT of abdomen and pelvis"
    """
    if not study:
        return study
    
    # Extract modality (MRI, CT, X-ray, etc.)
    modality_match = re.search(r"\b(MRI|CT|X-RAY|ULTRASOUND|MAMMOGRAM|PET|ANGIOGRAPHY|FLUOROSCOPY)\b", study, re.IGNORECASE)
    if not modality_match:
        return study  # Can't simplify if no modality found
    
    modality = modality_match.group(1).upper()
    if modality == "X-RAY":
        modality = "X-ray"
    
    # Extract body region - look for common anatomical terms
    body_regions = {
        r"\b(lumbar|lower back|L[\s-]?spine)\b": "lumbar spine",
        r"\b(cervical|neck|C[\s-]?spine)\b": "cervical spine",
        r"\b(thoracic|T[\s-]?spine)\b": "thoracic spine",
        r"\b(spine|spinal)\b": "spine",
        r"\b(brain|head|cranial)\b": "brain",
        r"\b(chest|thorax|lung)\b": "chest",
        r"\b(abdomen|abdominal|tummy|belly)\b": "abdomen",
        r"\b(pelvis|pelvic)\b": "pelvis",
        r"\b(knee)\b": "knee",
        r"\b(shoulder)\b": "shoulder",
        r"\b(hip)\b": "hip",
        r"\b(ankle)\b": "ankle",
        r"\b(foot|feet)\b": "foot",
        r"\b(hand)\b": "hand",
        r"\b(wrist)\b": "wrist",
        r"\b(elbow)\b": "elbow",
    }
    
    regions_found = []
    for pattern, region_name in body_regions.items():
        if re.search(pattern, study, re.IGNORECASE):
            if region_name not in regions_found:
                regions_found.append(region_name)
    
    # Contrast detection
    contrast = ""
    if re.search(r"\b(without contrast|non-contrast|without dye|no contrast)\b", study, re.IGNORECASE):
        contrast = " (non-contrast)"
    elif re.search(r"\b(with contrast|with iv contrast|with dye)\b", study, re.IGNORECASE):
        contrast = " (with contrast)"

    if regions_found:
        region_str = " and ".join(regions_found)
        return f"{modality} of {region_str}{contrast}"
    else:
        # Fallback: just return the modality if we can't identify body region
        return f"{modality}{contrast}"

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

    # Study type detection - extract from Procedure Details section first
    study = ""
    
    # Strategy 1: Look for "Procedure Details" or similar headers and extract the description
    # This captures the full description like "CT (special x-ray) of your chest..."
    proc_match = re.search(
        r"(?im)^(?:PROCEDURE\s+DETAILS?|EXAMINATION|STUDY|EXAM)(?:[:\s]*)\n+([^\n]{10,150})",
        t
    )
    if proc_match:
        study = proc_match.group(1).strip()
    
    # Strategy 2: If header had content on same line (e.g., "EXAMINATION: CT Chest")
    if not study:
        m = re.search(r"(?im)^(?:EXAMINATION|STUDY|PROCEDURE|EXAM)(?:\s+DETAILS)?[:\s]+([^\n]{3,100})", t)
        if m:
            study = m.group(1).strip()
    
    # Strategy 3: Fallback to detecting modality keywords at start of line
    if not study:
        m = re.search(r"(?im)^(CT|MRI|X[- ]?RAY|ULTRASOUND|USG|MAMMOGRAM|PET|ANGIOGRAPHY|FLUOROSCOPY)[^\n]{0,80}", t)
        if m:
            study = m.group(0).strip()
    
    # Simplify verbose study descriptions to concise format (e.g., "MRI of lumbar spine")
    if study:
        study = _simplify_study_name(study)

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