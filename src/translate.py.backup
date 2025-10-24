# src/translate.py# src/translate.py# src/translate.py

from __future__ import annotations

from __future__ import annotationsfrom __future__ import annotations

import ast

import csv

import json

import loggingimport astimport csv, re, os, json, logging, time

import os

import reimport csvfrom dataclasses import dataclass

import time

from dataclasses import dataclassimport jsonfrom typing import Dict, List, Tuple

from typing import Dict, List, Tuple

import loggingfrom openai import BadRequestError, NotFoundError

from openai import BadRequestError, NotFoundError

import osimport ast

logger = logging.getLogger("insideimaging")

if not logger.handlers:import re

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

import time# ---------- logging ----------

try:

    from .parse import parse_metadata, sections_from_textfrom dataclasses import dataclasslogger = logging.getLogger("insideimaging")

except Exception:

    logger.warning("parse.py unavailable; using fallback metadata parsers")from typing import Dict, List, Tupleif not logger.handlers:



    def parse_metadata(text: str) -> Dict[str, str]:    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

        blob = text or ""

from openai import BadRequestError, NotFoundError

        def grab(pattern: str, default: str = "") -> str:

            match = re.search(pattern, blob, flags=re.I | re.M)# ---------- parse import with safe fallbacks ----------

            return match.group(1).strip() if match else default

logger = logging.getLogger("insideimaging")try:

        name = grab(r"^\s*NAME\s*:\s*([^\n]+)")

        age = grab(r"^\s*AGE\s*:\s*([0-9]{1,3})")if not logger.handlers:    from .parse import parse_metadata, sections_from_text

        sex_raw = grab(r"^\s*SEX\s*:\s*([MF]|Male|Female)")

        sex = {"m": "M", "f": "F", "male": "M", "female": "F"}.get(sex_raw.lower(), sex_raw) if sex_raw else ""    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")except Exception:

        date = grab(r"^\s*DATE\s*:\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})")

        study = grab(r"^\s*((?:MRI|CT|X-?RAY|ULTRASOUND|USG)[^\n]*)")    logger.warning("parse.py unavailable; using robust fallbacks")

        hospital = grab(r"^[^\n]*HOSPITAL[^\n]*$")

        return {"name": name, "age": age, "sex": sex, "hospital": hospital, "date": date, "study": study}# ---------------------------------------------------------------------------



    def sections_from_text(text: str) -> Dict[str, str]:# Robust section + metadata parsing fallbacks    def parse_metadata(text: str) -> Dict[str, str]:

        blob = text or ""

        pattern = re.compile(# ---------------------------------------------------------------------------        t = text or ""

            r"(?im)^\s*(clinical\s*history|history|indication|reason|technique|procedure(?:\s+and\s+findings)?|findings?|impression|conclusion|summary)\s*:\s*"

        )try:        def grab(rx, default=""):

        sections: Dict[str, str] = {"reason": "", "technique": "", "findings": "", "impression": ""}

        matches = [(m.group(1).lower(), m.start(), m.end()) for m in pattern.finditer(blob)]    from .parse import parse_metadata, sections_from_text            m = re.search(rx, t, flags=re.I | re.M)

        if not matches:

            sections["findings"] = blob.strip()except Exception:  # pragma: no cover - only hit if optional parser missing            return (m.group(1).strip() if m else default)

            return sections

        matches.append(("__END__", len(blob), len(blob)))    logger.warning("parse.py unavailable; using fallback metadata parsers")        name = grab(r"^\s*NAME\s*:\s*([^\n]+)")

        for index in range(len(matches) - 1):

            label, _, start = matches[index]        age = grab(r"^\s*AGE\s*:\s*([0-9]{1,3})")

            next_start = matches[index + 1][1]

            body = blob[start:next_start].strip()    def parse_metadata(text: str) -> Dict[str, str]:  # type: ignore[redef]        sex_raw = grab(r"^\s*SEX\s*:\s*([MF]|Male|Female)")

            if not body:

                continue        blob = text or ""        sex = {"m":"M","f":"F","male":"M","female":"F"}.get(sex_raw.lower(), sex_raw) if sex_raw else ""

            if label in ("clinical history", "history", "indication", "reason"):

                sections["reason"] = (sections["reason"] + " " + body).strip()        date = grab(r"^\s*DATE\s*:\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})")

            elif label.startswith("technique"):

                sections["technique"] = (sections["technique"] + " " + body).strip()        def grab(rx: str, default: str = "") -> str:        study = grab(r"^\s*((?:MRI|CT|X-?RAY|ULTRASOUND|USG)[^\n]*)")

            elif label.startswith("procedure") or label.startswith("finding"):

                sections["findings"] = (sections["findings"] + " " + body).strip()            m = re.search(rx, blob, flags=re.I | re.M)        hospital = grab(r"^[^\n]*HOSPITAL[^\n]*$")

            elif label in ("impression", "conclusion", "summary"):

                sections["impression"] = (sections["impression"] + " " + body).strip()            return (m.group(1).strip() if m else default)        return {"name": name, "age": age, "sex": sex, "hospital": hospital, "date": date, "study": study}

        return {key: value.strip() for key, value in sections.items()}





@dataclass        name = grab(r"^\s*NAME\s*:\s*([^\n]+)")    def sections_from_text(text: str) -> Dict[str, str]:

class Glossary:

    mapping: Dict[str, str]        age = grab(r"^\s*AGE\s*:\s*([0-9]{1,3})")        t = (text or "")



    @classmethod        sex_raw = grab(r"^\s*SEX\s*:\s*([MF]|Male|Female)")        pat = re.compile(

    def load(cls, path: str) -> "Glossary":

        data: Dict[str, str] = {}        sex = {"m": "M", "f": "F", "male": "M", "female": "F"}.get(sex_raw.lower(), sex_raw) if sex_raw else ""            r"(?im)^\s*(clinical\s*history|history|indication|reason|technique|procedure(?:\s+and\s+findings)?|findings?|impression|conclusion|summary)\s*:\s*"

        try:

            with open(path, newline="", encoding="utf-8-sig") as handle:        date = grab(r"^\s*DATE\s*:\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})")        )

                for row in csv.reader(handle):

                    if len(row) < 2:        study = grab(r"^\s*((?:MRI|CT|X-?RAY|ULTRASOUND|USG)[^\n]*)")        parts: Dict[str, str] = {"reason":"", "technique":"", "findings":"", "impression":""}

                        continue

                    key = (row[0] or "").strip().lower()        hospital = grab(r"^[^\n]*HOSPITAL[^\n]*$")        hits = [(m.group(1).lower(), m.start(), m.end()) for m in pat.finditer(t)]

                    value = (row[1] or "").strip()

                    if key:        return {"name": name, "age": age, "sex": sex, "hospital": hospital, "date": date, "study": study}        if not hits:

                        data[key] = value

        except Exception:            return parts | {"findings": t.strip()}

            logger.exception("glossary load failed")

        return cls(data)    def sections_from_text(text: str) -> Dict[str, str]:  # type: ignore[redef]        hits.append(("__END__", len(t), len(t)))



    def replace_terms(self, text: str) -> str:        blob = text or ""        for i in range(len(hits)-1):

        if not text:

            return ""        pattern = re.compile(            label, _, end = hits[i]

        output = text

        for key, value in self.mapping.items():            r"(?im)^\s*(clinical\s*history|history|indication|reason|technique|procedure(?:\s+and\s+findings)?|findings?|impression|conclusion|summary)\s*:\s*"            next_start = hits[i+1][1]

            output = re.sub(rf"\b{re.escape(key)}\b", value, output, flags=re.I)

        return output        )            body = t[end:next_start].strip()



        sections: Dict[str, str] = {"reason": "", "technique": "", "findings": "", "impression": ""}            if not body:

@dataclass

class ReportMetadata:        matches = [(m.group(1).lower(), m.start(), m.end()) for m in pattern.finditer(blob)]                continue

    name: str = ""

    age: str = ""        if not matches:            if label in ("clinical history","history","indication","reason"):

    sex: str = ""

    hospital: str = ""            sections["findings"] = blob.strip()                parts["reason"] = (parts["reason"] + " " + body).strip()

    date: str = ""

    study: str = ""            return sections            elif label.startswith("technique"):

    history: str = ""

        matches.append(("__END__", len(blob), len(blob)))                parts["technique"] = (parts["technique"] + " " + body).strip()



@dataclass        for idx in range(len(matches) - 1):            elif label.startswith("procedure") or label.startswith("finding"):

class ReportSections:

    reason: str = ""            label, _, start = matches[idx]                parts["findings"] = (parts["findings"] + " " + body).strip()

    technique: str = ""

    findings: str = ""            next_start = matches[idx + 1][1]            elif label in ("impression","conclusion","summary"):

    impression: str = ""

    raw_text: str = ""            body = blob[start:next_start].strip()                parts["impression"] = (parts["impression"] + " " + body).strip()



            if not body:        return {k:v.strip() for k,v in parts.items()}

_PHI_STOPWORDS = {

    "hospital",                continue

    "clinic",

    "centre",            if label in ("clinical history", "history", "indication", "reason"):# ---------- glossary ----------

    "center",

    "medical",                sections["reason"] = (sections["reason"] + " " + body).strip()@dataclass

    "radiology",

    "imaging",            elif label.startswith("technique"):class Glossary:

    "ct",

    "mri",                sections["technique"] = (sections["technique"] + " " + body).strip()    mapping: Dict[str, str]

    "xray",

    "x-ray",            elif label.startswith("procedure") or label.startswith("finding"):    @classmethod

    "scan",

    "study",                sections["findings"] = (sections["findings"] + " " + body).strip()    def load(cls, path: str) -> "Glossary":

    "male",

    "female",            elif label in ("impression", "conclusion", "summary"):        m: Dict[str, str] = {}

    "sex",

    "age",                sections["impression"] = (sections["impression"] + " " + body).strip()        try:

    "date",

    "mrn",        return {k: v.strip() for k, v in sections.items()}            with open(path, newline="", encoding="utf-8-sig") as f:

    "patient",

    "ref",                for row in csv.reader(f):

    "number",

    "id",                    if len(row) >= 2:

    "account",

    "acct",# ---------------------------------------------------------------------------                        k = (row[0] or "").strip().lower()

    "doctor",

    "dr",# Domain-level containers                        v = (row[1] or "").strip()

}

                _PHI_STOPWORDS = {

_PHI_PLACEHOLDERS = {                    "hospital",

    "[REDACTED]": "the patient",                    "clinic",

    "[DOB]": "date withheld",                    "centre",

    "[AGE]": "age withheld",                    "center",

    "[SEX]": "sex withheld",                    "medical",

    "[AGE/SEX]": "age/sex withheld",                    "radiology",

}                    "imaging",

                    "ct",

                    "mri",

def _tokenise_phi(value: str) -> List[str]:                    "xray",

    tokens: List[str] = []                    "x-ray",

    cleaned = re.sub(r"\s+", " ", (value or "").strip())                    "scan",

    if cleaned:                    "study",

        tokens.append(cleaned)                    "male",

    for piece in re.split(r"[:;,_-]+", cleaned):                    "female",

        piece = piece.strip()                    "sex",

        if len(piece) < 2:                    "age",

            continue                    "date",

        if piece.lower() in _PHI_STOPWORDS:                    "mrn",

            continue                    "patient",

        if not re.search(r"[A-Za-z]", piece):                    "ref",

            continue                    "number",

        tokens.append(piece)                    "id",

    return tokens                    "account",

                    "acct",

                    "doctor",

def _collect_phi_terms(meta: ReportMetadata) -> List[str]:                    "dr",

    terms: List[str] = []                }

    for value in (meta.name, meta.hospital, meta.date):# ---------------------------------------------------------------------------                        if k:

        if value:

            terms.extend(_tokenise_phi(value))@dataclass                            m[k] = v

    return terms

class Glossary:        except Exception:



def _redact_phi(text: str, extra_terms: List[str]) -> str:    mapping: Dict[str, str]            logger.exception("glossary load failed")

    blob = text or ""

    blob = re.sub(        return cls(m)

        r"(?im)^\s*(name|patient|pt|mrn|id|acct|account|gender|sex|age|dob|date\s+of\s+birth)\s*[:#].*$",

        "[REDACTED]",    @classmethod    def replace_terms(self, text: str) -> str:

        blob,

    )    def load(cls, path: str) -> "Glossary":        if not text:

    blob = re.sub(r"(?i)\bDOB\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[DOB]", blob)

    blob = re.sub(r"(?i)\b(date\s+of\s+birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[DOB]", blob)        data: Dict[str, str] = {}            return ""

    blob = re.sub(r"(?i)\b(\d{1,3})\s*(?:year[- ]?old|y/o|yo|yrs?|years?)\b", "[AGE]", blob)

    blob = re.sub(r"(?i)\b(?:male|female)\b", "[SEX]", blob)        try:        out = text

    blob = re.sub(r"(?i)\b(\d{1,3})\s*/\s*(m|f)\b", "[AGE/SEX]", blob)

    blob = re.sub(r"(?i)\b(\d{1,3})(m|f)\b", "[AGE/SEX]", blob)            with open(path, newline="", encoding="utf-8-sig") as handle:        for k, v in self.mapping.items():

    for term in extra_terms or []:

        term = term.strip()                for row in csv.reader(handle):            out = re.sub(rf"\b{re.escape(k)}\b", v, out, flags=re.I)

        if not term:

            continue                    if len(row) < 2:        return out

        blob = re.sub(rf"(?i){re.escape(term)}", "[REDACTED]", blob)

    return blob                        continue



                    key = (row[0] or "").strip().lower()# ---------- vocab ----------

def _normalise_placeholders(text: str) -> str:

    output = text or ""                    value = (row[1] or "").strip()POS_WORDS = ["normal","benign","unremarkable","clear","symmetric","intact","stable","improved","no ","without "]

    for placeholder, replacement in _PHI_PLACEHOLDERS.items():

        output = output.replace(placeholder, replacement)                    if key:NEG_WORDS = [

    return output

                        data[key] = value    "mass","tumor","cancer","lesion","adenopathy","enlarged","necrotic","metastasis",



_MEASUREMENT_BLOCK = re.compile(        except Exception:    "obstruction","compression","invasion","perforation","ischemia","fracture","bleed",

    r"((?:\d+(?:\.\d+)?)(?:\s*[x×]\s*(?:\d+(?:\.\d+)?)){1,3})\s*(mm|cm)\b",

    flags=re.I,            logger.exception("glossary load failed")    "hydroureteronephrosis","hydroureter","hydronephrosis","herniation","shift","edema",

)

_SINGLE_MEASUREMENT = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", flags=re.I)        return cls(data)    "swelling","atrophy","stenosis","anomaly",



]

def _round_number(value: str) -> str:

    try:    def replace_terms(self, text: str) -> str:NEG_PHRASES = [r"mass\s+effect", r"subfalcine\s+herniation", r"midline\s+shift", r"perilesional\s+edema"]

        number = float(value)

    except ValueError:        if not text:NEG_DEFS: Dict[str, str] = {

        return value

    if abs(number) >= 10:            return ""    "mass":"an abnormal lump that can press on tissue","tumor":"a growth that forms a lump","cancer":"a harmful growth that can spread",

        return str(int(round(number)))

    return f"{round(number, 1):g}"        result = text    "lesion":"an abnormal spot or area","adenopathy":"swollen lymph nodes","enlarged":"bigger than normal","necrotic":"dead tissue",



        for key, value in self.mapping.items():    "metastasis":"spread to other areas","obstruction":"a blockage","compression":"being pressed or squeezed by something","invasion":"growing into nearby tissues",

def _convert_measurements(text: str) -> str:

    def convert_block(match: re.Match) -> str:            result = re.sub(rf"\b{re.escape(key)}\b", value, result, flags=re.I)    "perforation":"a hole or tear","ischemia":"low blood flow","fracture":"a broken bone","bleed":"bleeding","herniation":"disc material pushed out of place",

        numbers = re.split(r"\s*[x×]\s*", match.group(1))

        unit = match.group(2).lower()        return result    "edema":"swelling with fluid buildup","atrophy":"shrinking or wasting of tissue","stenosis":"narrowing of a passage or canal","anomaly":"difference from typical anatomy",

        converted: List[str] = []

        if unit == "mm":    "mass effect":"pressure on brain structures","subfalcine herniation":"brain shifted under the central fold","midline shift":"brain pushed off center",

            for number in numbers:

                try:    "perilesional edema":"swelling around the lesion",

                    value = float(number)

                except ValueError:@dataclass    # spine-specific

                    converted.append(number)

                    continueclass ReportMetadata:    "disc bulge":"disc cushion pushed out beyond normal boundaries","nerve root":"nerve branch exiting the spinal cord",

                if value >= 10:

                    converted.append(f"{round(value / 10.0, 1):g}")    name: str = ""    "foraminal narrowing":"smaller space where nerve exits the spine","spinal canal":"tunnel that protects the spinal cord",

                else:

                    converted.append(f"{round(value, 1):g} mm")    age: str = ""    "bilateral":"on both sides","unilateral":"on one side only","posterior":"toward the back","anterior":"toward the front",

            if all("mm" not in part for part in converted):

                return " x ".join(converted) + " cm"    sex: str = ""    "degenerative":"wear and tear from aging or use","vertebra":"individual spine bone","intervertebral":"between spine bones",

            return " x ".join(converted)

        for number in numbers:    hospital: str = ""}

            converted.append(_round_number(number))

        return " x ".join(converted) + " cm"    date: str = ""



    def convert_single(match: re.Match) -> str:    study: str = ""# ---------- plain-language rewrites ----------

        value = float(match.group(1))

        unit = match.group(2).lower()    history: str = ""_JARGON_MAP = [

        if unit == "mm" and value >= 10:

            return f"{round(value / 10.0, 1):g} cm"    (re.compile(r"\bsubfalcine\s+herniation\b", re.I), "subfalcine herniation, brain shift under the central fold"),

        if unit == "cm" and value < 0.1:

            return f"{round(value * 10.0, 1):g} mm"    (re.compile(r"\bperilesional\b", re.I), "around the lesion"),

        return f"{_round_number(match.group(1))} {unit}"

@dataclass    (re.compile(r"\bparenchymal\b", re.I), "brain tissue"),

    text = _MEASUREMENT_BLOCK.sub(convert_block, text or "")

    return _SINGLE_MEASUREMENT.sub(convert_single, text)class ReportSections:    (re.compile(r"\bavid(ly)?\s+enhanc(?:ing|ement)\b|\bavid(ly)?\s+enhacing\b", re.I), "enhances with contrast dye"),



    reason: str = ""    (re.compile(r"\bhyperintense\b", re.I), "brighter on the scan"),

_JARGON_MAP = [

    (re.compile(r"\bheterogene(?:ous|ity)\b", re.I), "mixed in appearance"),    technique: str = ""    (re.compile(r"\bhypointense\b", re.I), "darker on the scan"),

    (re.compile(r"\bhypoattenuating\b", re.I), "darker on the scan"),

    (re.compile(r"\bhyperattenuating\b", re.I), "brighter on the scan"),    findings: str = ""    (re.compile(r"\bhyperdense\b", re.I), "brighter on the scan"),

    (re.compile(r"\bhyperintense\b", re.I), "brighter on the scan"),

    (re.compile(r"\bhypointense\b", re.I), "darker on the scan"),    impression: str = ""    (re.compile(r"\bhypodense\b", re.I), "darker on the scan"),

    (re.compile(r"\blesion\b", re.I), "abnormal area"),

    (re.compile(r"\badenopathy\b", re.I), "swollen lymph nodes"),    raw_text: str = ""    (re.compile(r"\benhancing\b", re.I), "lighting up after dye"),

    (re.compile(r"\bdilat(?:ation|ed)\b", re.I), "widened"),

    (re.compile(r"\bstenosis\b", re.I), "narrowing"),    (re.compile(r"\bnon[-\s]?enhancing\b", re.I), "not lighting up after dye"),

    (re.compile(r"\bobstruction\b", re.I), "blockage"),

    (re.compile(r"\bperi[-\s]?lesional\b", re.I), "around the abnormal area"),    (re.compile(r"\bheterogene(?:ous|ity)\b", re.I), "mixed appearance"),

    (re.compile(r"\bextra[-\s]?axial\b", re.I), "outside the brain tissue"),

]# ---------------------------------------------------------------------------    (re.compile(r"\bfoci\b", re.I), "spots"),



_TERMINOLOGY = {# Sanitisation helpers    (re.compile(r"\bnodular\b", re.I), "lumpy"),

    "unremarkable": "looks normal",

    "intact": "normal",# ---------------------------------------------------------------------------    (re.compile(r"\blesion\b", re.I), "lesion (abnormal area)"),

    "benign": "not dangerous",

    "symmetric": "the same on both sides",_PHI_STOPWORDS = {    (re.compile(r"\bextra[-\s]?axial\b", re.I), "outside the brain tissue"),

    "heterogenous": "mixed in appearance",

    "hyperdense": "brighter on the scan",    "hospital",    (re.compile(r"\beffaced?\b", re.I), "pressed"),

    "hypodense": "darker on the scan",

    "enhancing": "lighting up after dye",    "clinic",    (re.compile(r"\bdilated\b", re.I), "widened"),

}

    "centre",    (re.compile(r"\bemerging\s+from\s+the\b", re.I), "near the"),



def _simplify_sentence(text: str) -> str:    "center",    (re.compile(r"\bedema\b", re.I), "swelling"),

    sentence = _convert_measurements(text or "")

    for pattern, repl in _JARGON_MAP:    "medical",    (re.compile(r"\buvimbe\b", re.I), "mass"),

        sentence = pattern.sub(repl, sentence)

    for key, value in _TERMINOLOGY.items():    "radiology",    # spine

        sentence = re.sub(rf"(?i)\b{re.escape(key)}\b", value, sentence)

    sentence = re.sub(r"\s{2,}", " ", sentence)    "imaging",    (re.compile(r"\bhypolordosis\b", re.I), "reduced normal neck curve"),

    sentence = sentence.replace(" ,", ",").replace(" .", ".")

    sentence = sentence.strip()    "ct",    (re.compile(r"\blordosis\b", re.I), "inward spine curve"),

    if sentence and not sentence[0].isupper():

        sentence = sentence[0].upper() + sentence[1:]    "mri",    (re.compile(r"\bkyphosis\b", re.I), "forward rounding of the spine"),

    return sentence

    "xray",    (re.compile(r"\bdisc\s+herniation\b", re.I), "disc bulge"),



def _split_sentences(text: str) -> List[str]:    "x-ray",    (re.compile(r"\bprotrusion\b", re.I), "bulge"),

    normalised = re.sub(r"\s+", " ", text or "").strip()

    if not normalised:    "scan",    (re.compile(r"\bcalvarium\b", re.I), "skull bones"),

        return []

    parts = re.split(r"(?<=[.!?])\s+", normalised)    "study",    (re.compile(r"\bcervical\b", re.I), "neck"),

    return [part.strip() for part in parts if part.strip()]

    "male",    (re.compile(r"\bforamina?\b", re.I), "nerve openings"),



_NEGATIVE_TERMS = {    "female",    (re.compile(r"\buvunjaji\b", re.I), "fracture"),

    "mass": "an abnormal lump that can press on tissue",

    "lesion": "an abnormal area",    "sex",    (re.compile(r"\bischemi(?:a|c)\b", re.I), "low blood flow"),

    "tumor": "a growth that forms a lump",

    "tumour": "a growth that forms a lump",    "age",    (re.compile(r"\bperfusion\b", re.I), "blood flow"),

    "cancer": "a harmful growth that can spread",

    "obstruction": "a blockage",    "date",    (re.compile(r"\bembol(?:us|i|ism)\b", re.I), "blood clot"),

    "blockage": "a blockage",

    "stenosis": "narrowing of a passage",    "mrn",    (re.compile(r"\bstenosis\b", re.I), "narrowing"),

    "fracture": "a broken bone",

    "hemorrhage": "bleeding",    "patient",]

    "haemorrhage": "bleeding",

    "edema": "swelling from fluid buildup",    "ref",def _rewrite_jargon(s: str) -> str:

    "dilation": "widening",

    "dilatation": "widening",    "number",    out = s or ""

}

    "id",    for rx, repl in _JARGON_MAP:

_NEGATIVE_PATTERNS = [re.compile(rf"(?i)\b{term}\b") for term in _NEGATIVE_TERMS]

_POSITIVE_PATTERN = re.compile(r"(?i)\b(no\s+evidence\b|no\s+significant|normal|benign|without)\b")    "account",        out = rx.sub(repl, out)



    "acct",    return out

def _wrap_pos(text: str) -> str:

    return f'<span class="ii-pos" style="color:#22c55e;font-weight:600">{text}</span>'    "doctor",



    "dr",# ---------- tooltips ----------

def _wrap_neg(term: str, definition: str = "") -> str:

    data = f' data-def="{definition.replace("\"", "&quot;")}"' if definition else ""}_TERM_DEFS = [

    return f'<span class="ii-neg" style="color:#ef4444;font-weight:600"{data}>{term}</span>'

    {"pat": r"\bmeningioma\b", "def": "tumor from the brain’s lining"},



def _highlight_sentence(text: str) -> str:_PHI_PLACEHOLDERS = {    {"pat": r"\bextra[-\s]?axial\b", "def": "outside brain tissue but inside skull"},

    if not text:

        return ""    "[REDACTED]": "the patient",    {"pat": r"\bsubfalcine\s+herniation\b", "def": "brain pushed under central fold"},

    output = text

    for pattern in _NEGATIVE_PATTERNS:    "[DOB]": "date withheld",    {"pat": r"\bmass\s+effect\b", "def": "pressure or shift caused by a mass"},

        def repl(match: re.Match) -> str:

            token = match.group(0)    "[AGE]": "age withheld",    {"pat": r"\bperilesional\s+edema\b", "def": "swelling around a lesion"},

            definition = _NEGATIVE_TERMS.get(token.lower(), "")

            return _wrap_neg(token, definition)    "[SEX]": "sex withheld",    {"pat": r"\bgreater\s+sphenoid\s+wing\b", "def": "part of skull bone near the temple"},

        output = pattern.sub(repl, output)

    output = _POSITIVE_PATTERN.sub(lambda m: _wrap_pos(m.group(0)), output)    "[AGE/SEX]": "age/sex withheld",    {"pat": r"\bventricle[s]?\b", "def": "fluid spaces inside the brain"},

    return f'<span class="ii-text" style="color:#ffffff">{output}</span>'

}    # spine



def _render_bullets(items: List[str], include_normal: bool, language: str) -> str:    {"pat": r"\bhypolordosis\b", "def": "reduced normal inward curve of the neck"},

    processed: List[str] = []

    for sentence in items:    {"pat": r"\bdisc\s+bulge\b", "def": "disc cushion pushed outward beyond normal boundaries"},

        simplified = _simplify_sentence(sentence)

        if not simplified:def _tokenise_phi(value: str) -> List[str]:    {"pat": r"\bdisc\s+herniation\b", "def": "disc material pushed out of its normal position"},

            continue

        processed.append(_highlight_sentence(simplified))    terms: List[str] = []    {"pat": r"\bforamina?\b", "def": "openings where nerves exit the spinal canal"},

    if include_normal:

        normal = "Most other areas look normal." if language.lower() not in ("kiswahili", "swahili") else "Maeneo mengine yanaonekana kawaida."    cleaned = re.sub(r"\s+", " ", (value or "").strip())    {"pat": r"\bforaminal\s+narrowing\b", "def": "smaller space where nerve exits, potentially pinching the nerve"},

        processed.append(_highlight_sentence(normal))

    if not processed:    if cleaned:    {"pat": r"\bnerve\s+root\s+compression\b", "def": "nerve branch being squeezed as it exits the spine"},

        fallback = "No major problems were seen." if language.lower() not in ("kiswahili", "swahili") else "Hakuna matatizo makubwa yaliyoonekana."

        processed.append(_highlight_sentence(fallback))        terms.append(cleaned)    {"pat": r"\bspinal\s+canal\s+stenosis\b", "def": "narrowing of the tunnel that protects the spinal cord"},

    return "<ul class='ii-list' style='color:#ffffff'>" + "".join(f"<li>{item}</li>" for item in processed[:5]) + "</ul>"

    for piece in re.split(r"[:;,_-]+", cleaned):    {"pat": r"\bspondylosis\b", "def": "spine wear and tear from aging"},



_KISWAHILI_FALLBACKS = {        piece = piece.strip()    {"pat": r"\bosteophyte\b", "def": "bone spur - extra bone growth"},

    "Technique not described.": "Mbinu haijaelezewa.",

    "The scan was ordered to look for a problem in the area.": "Skani iliagizwa kutafuta tatizo katika eneo hili.",        if len(piece) < 2:    {"pat": r"\bcalvarium\b", "def": "skull bones over the brain"},

    "Most other areas look normal.": "Maeneo mengine yanaonekana kawaida.",

    "No major problems were seen.": "Hakuna matatizo makubwa yaliyoonekana.",            continue    {"pat": r"\bvertebral\s+body\b", "def": "main cylindrical part of a spine bone"},

    "Please talk to your doctor about the next steps.": "Tafadhali zungumza na daktari wako kuhusu hatua zinazofuata.",

}        if piece.lower() in _PHI_STOPWORDS:    {"pat": r"\bintervertebral\s+disc\b", "def": "cushion between spine bones"},



            continue    {"pat": r"\bdegenerative\s+change", "def": "wear and tear from normal aging"},

def _maybe_translate_sentence(sentence: str, language: str) -> str:

    if language.lower() not in ("kiswahili", "swahili"):        if not re.search(r"[A-Za-z]", piece):    {"pat": r"\bposterior\b", "def": "toward the back"},

        return sentence

    return _KISWAHILI_FALLBACKS.get(sentence, sentence)            continue    {"pat": r"\banterior\b", "def": "toward the front"},



        terms.append(piece)    {"pat": r"\bbilateral\b", "def": "on both sides"},

_JSON_KEYS = ["reason", "technique", "findings", "conclusion", "concern"]

    return terms    {"pat": r"\bunilateral\b", "def": "on one side only"},



def _resolve_models() -> Tuple[str, str]:    {"pat": r"\blumbar\b", "def": "lower back region"},

    env_model = os.getenv("OPENAI_MODEL", "gpt-5")

    fallback = os.getenv("OPENAI_CHAT_FALLBACK", "gpt-4o-mini")    {"pat": r"\bcervical\b", "def": "neck region"},

    return env_model, fallback

def _collect_phi_terms(meta: ReportMetadata) -> List[str]:    {"pat": r"\bthoracic\b", "def": "mid-back region"},



def _supports_chat(model: str) -> bool:    terms: List[str] = []    {"pat": r"\bconus\s+medullaris\b", "def": "tapered end of the spinal cord"},

    lower = (model or "").lower()

    return any(token in lower for token in ["gpt-4", "gpt-4o", "4o-mini", "gpt-3.5", "mini", "o1"])    for val in (meta.name, meta.hospital, meta.date):    {"pat": r"\bligamentum\s+flavum\b", "def": "elastic ligament connecting vertebrae"},



        if val:    {"pat": r"\bfacet\s+joint\b", "def": "small joint between spine bones"},

def _call_openai(text: str, language: str) -> Dict[str, str] | None:

    from openai import OpenAI            terms.extend(_tokenise_phi(val))    {"pat": r"\buvunjaji\b", "def": "fracture"},



    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))    return terms    # commonly missing definitions

    env_model, chat_fallback = _resolve_models()

    {"pat": r"\bhydroureteronephrosis\b", "def": "swelling of kidney and ureter from blocked urine"},

    if language.lower() in ("kiswahili", "swahili"):

        instructions = (    {"pat": r"\bhydronephrosis\b", "def": "kidney swelling from blocked urine"},

            "Wewe ni msaidizi wa kutoa muhtasari wa ripoti za uchunguzi wa mwili. "

            "Toa matokeo kwa Kiswahili rahisi. Rudisha tu JSON iliyo na funguo reason, technique, findings, conclusion, concern."def _redact_phi(text: str, extra_terms: List[str]) -> str:    {"pat": r"\bhydroureter\b", "def": "ureter swelling from blocked urine"},

        )

    else:    blob = text or ""    {"pat": r"\badenopathy\b", "def": "swollen lymph nodes"},

        instructions = (

            "You summarise medical imaging reports for patients. "    blob = re.sub(    {"pat": r"\bnecrotic\b", "def": "dead tissue"},

            "Return ONLY JSON with keys reason, technique, findings, conclusion, concern. "

            "Explain medical jargon in parentheses and keep numbers exactly as written."        r"(?im)^\s*(name|patient|pt|mrn|id|acct|account|gender|sex|age|dob|date\s+of\s+birth)\s*[:#].*$",    {"pat": r"\bmetastasis\b", "def": "cancer spread to other areas"},

        )

        "[REDACTED]",    {"pat": r"\bobstruction\b", "def": "blockage"},

    system_message = {"role": "system", "content": instructions}

    user_message = {"role": "user", "content": text.strip()}        blob,    {"pat": r"\bcompression\b", "def": "being squeezed or pressed"},



    try:    )    {"pat": r"\binvasion\b", "def": "growth spreading into nearby tissues"},

        if _supports_chat(env_model):

            response = client.chat.completions.create(    blob = re.sub(r"(?i)\bDOB\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[DOB]", blob)    {"pat": r"\bperforation\b", "def": "hole or tear in tissue"},

                model=env_model,

                messages=[system_message, user_message],    blob = re.sub(r"(?i)\b(date\s+of\s+birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "[DOB]", blob)    {"pat": r"\bischemia\b", "def": "reduced blood flow"},

                temperature=0.2,

                response_format={"type": "json_object"},    blob = re.sub(r"(?i)\b(\d{1,3})\s*(?:year[- ]?old|y/o|yo|yrs?|years?)\b", "[AGE]", blob)    {"pat": r"\batrophy\b", "def": "tissue shrinking or wasting away"},

                timeout=90,

            )    blob = re.sub(r"(?i)\b(?:male|female)\b", "[SEX]", blob)    {"pat": r"\bstenosis\b", "def": "narrowing of a passage"},

            return json.loads(response.choices[0].message.content or "{}")

        response = client.responses.create(    blob = re.sub(r"(?i)\b(\d{1,3})\s*/\s*(m|f)\b", "[AGE/SEX]", blob)    # Additional commonly missing medical terms

            model=env_model,

            input=[system_message, user_message],    blob = re.sub(r"(?i)\b(\d{1,3})(m|f)\b", "[AGE/SEX]", blob)    {"pat": r"\bparenchyma\b", "def": "the functional tissue of an organ"},

            response_format={"type": "json_object"},

            temperature=0.2,    if extra_terms:    {"pat": r"\bcortex\b", "def": "the outer layer of an organ"},

            timeout=90,

        )        for term in extra_terms:    {"pat": r"\bmedulla\b", "def": "the inner part of an organ"},

        content = response.output[0].content[0].text if response.output else "{}"

        return json.loads(content or "{}")            term = term.strip()    {"pat": r"\blumen\b", "def": "the hollow space inside a tube or vessel"},

    except BadRequestError as exc:

        if chat_fallback and chat_fallback != env_model and "json" in (exc.message or "").lower():            if not term:    {"pat": r"\bmucosa\b", "def": "the moist inner lining of some organs"},

            try:

                response = client.chat.completions.create(                continue    {"pat": r"\bserosa\b", "def": "the smooth outer lining of organs"},

                    model=chat_fallback,

                    messages=[system_message, user_message],            blob = re.sub(rf"(?i){re.escape(term)}", "[REDACTED]", blob)    {"pat": r"\bcapsule\b", "def": "a membrane enclosing an organ"},

                    temperature=0.2,

                    response_format={"type": "json_object"},    return blob    {"pat": r"\bhilum\b", "def": "the area where vessels enter/exit an organ"},

                    timeout=90,

                )    {"pat": r"\bfistula\b", "def": "an abnormal connection between two body parts"},

                return json.loads(response.choices[0].message.content or "{}")

            except Exception:    {"pat": r"\banastomosis\b", "def": "a connection between two vessels or structures"},

                logger.exception("fallback chat completion failed")

        logger.exception("OpenAI BadRequestError")def _normalise_placeholders(text: str) -> str:    {"pat": r"\bembolism\b", "def": "blockage of a blood vessel by a clot or debris"},

    except NotFoundError:

        logger.exception("OpenAI model not found")    out = text or ""    {"pat": r"\bthrombus\b", "def": "a blood clot inside a vessel"},

    except Exception:

        logger.exception("Unexpected OpenAI failure")    for placeholder, replacement in _PHI_PLACEHOLDERS.items():    {"pat": r"\baneurysm\b", "def": "a bulge in a blood vessel wall"},

    return None

        out = out.replace(placeholder, replacement)    {"pat": r"\bocclusion\b", "def": "complete blockage of a passage"},



_REASON_HEADER = re.compile(r"(?im)^\s*(indication|reason|history|clinical\s+history)\s*:\s*(.+)$")    return out    {"pat": r"\binfarction\b", "def": "tissue death due to lack of blood supply"},



    {"pat": r"\bhemorrhage\b", "def": "bleeding"},

def _infer_reason(text: str, sections: ReportSections, metadata: ReportMetadata, language: str) -> str:

    if sections.reason:    {"pat": r"\bhematoma\b", "def": "collection of blood outside vessels"},

        stripped = re.sub(r"(?im)^\s*(indication|reason|history|clinical\s+history)\s*:\s*", "", sections.reason).strip()

        if stripped:# ---------------------------------------------------------------------------    {"pat": r"\bcontusion\b", "def": "a bruise"},

            sentence = stripped if stripped.endswith(".") else stripped + "."

            if not re.match(r"(?i)^(the|this|patient)", sentence.strip()):# Text normalisation utilities    {"pat": r"\blaceration\b", "def": "a cut or tear in tissue"},

                sentence = "The scan was ordered because " + sentence.lstrip()

            return _maybe_translate_sentence(_simplify_sentence(sentence), language)# ---------------------------------------------------------------------------    {"pat": r"\brupture\b", "def": "bursting or tearing of an organ or tissue"},

    match = _REASON_HEADER.search(text or "")

    if match:_MEASUREMENT_BLOCK = re.compile(    {"pat": r"\bprolapse\b", "def": "slipping of an organ from its normal position"},

        reason_text = match.group(2).strip()

        sentence = reason_text if reason_text.endswith(".") else reason_text + "."    r"((?:\d+(?:\.\d+)?)(?:\s*[x×]\s*(?:\d+(?:\.\d+)?)){1,3})\s*(mm|cm)\b",    {"pat": r"\beffusion\b", "def": "fluid buildup in a space"},

        return _maybe_translate_sentence(_simplify_sentence(sentence), language)

    default = "The scan was ordered to look for a problem in the area."    flags=re.I,    {"pat": r"\bascites\b", "def": "fluid buildup in the belly"},

    return _maybe_translate_sentence(default, language)

)    {"pat": r"\bedema\b", "def": "swelling from fluid buildup"},



def _infer_technique(text: str, sections: ReportSections, language: str) -> str:_SINGLE_MEASUREMENT = re.compile(r"\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", flags=re.I)    {"pat": r"\bsplenomegaly\b", "def": "enlarged spleen"},

    if sections.technique:

        sentences = _split_sentences(sections.technique)    {"pat": r"\bhepatomegaly\b", "def": "enlarged liver"},

        if sentences:

            joined = " ".join(_simplify_sentence(sentence) for sentence in sentences[:4])    {"pat": r"\bcardiomegaly\b", "def": "enlarged heart"},

            return _maybe_translate_sentence(joined, language)

    modality = "scan"def _round_number(value: str) -> str:    {"pat": r"\batelectasis\b", "def": "collapsed lung tissue"},

    if re.search(r"\bmri\b", text, flags=re.I):

        modality = "MRI scan"    try:    {"pat": r"\bpneumothorax\b", "def": "air in the chest cavity causing lung collapse"},

    elif re.search(r"\bct\b", text, flags=re.I):

        modality = "CT scan"        number = float(value)    {"pat": r"\bpleural effusion\b", "def": "fluid around the lung"},

    elif re.search(r"ultrasound", text, flags=re.I):

        modality = "Ultrasound"    except ValueError:    {"pat": r"\bconsolidation\b", "def": "lung tissue filled with fluid or pus"},

    body = metadata.study or "the area of concern"

    base = f"{modality} of {body.lower()} was performed."        return value    {"pat": r"\bopacity\b", "def": "an area that blocks X-rays (appears white)"},

    return _maybe_translate_sentence(_simplify_sentence(base), language)

    if abs(number) >= 10:    {"pat": r"\blucency\b", "def": "an area that allows X-rays through (appears dark)"},



def _extract_key_findings(sections: ReportSections) -> List[str]:        return str(int(round(number)))    {"pat": r"\bcalcification\b", "def": "calcium deposits in tissue"},

    pool = sections.findings or sections.raw_text

    pool = re.sub(r"(?im)^\s*(findings?|impression|conclusion|summary)\s*:\s*", "", pool)    return f"{round(number, 1):g}"    {"pat": r"\bsclerosis\b", "def": "hardening of tissue"},

    bullets: List[str] = []

    for line in pool.splitlines():    {"pat": r"\bfibrosis\b", "def": "scarring"},

        candidate = line.strip()

        if candidate:    {"pat": r"\bcirrhosis\b", "def": "severe liver scarring"},

            bullets.append(candidate)

    if not bullets:def _convert_measurements(text: str) -> str:    {"pat": r"\bneoplasm\b", "def": "abnormal growth or tumor"},

        bullets = _split_sentences(pool)

    return bullets[:6]    def convert_block(match: re.Match) -> str:    {"pat": r"\bmalignancy\b", "def": "cancer"},



        numbers = re.split(r"\s*[x×]\s*", match.group(1))    {"pat": r"\bbenign\b", "def": "not cancerous"},

def _extract_conclusion(sections: ReportSections) -> List[str]:

    text = sections.impression or ""        unit = match.group(2).lower()    {"pat": r"\bnodule\b", "def": "a small rounded lump"},

    if not text:

        return []        converted: List[str] = []    {"pat": r"\bcyst\b", "def": "a fluid-filled sac"},

    return _split_sentences(text)[:3]

        if unit == "mm":    {"pat": r"\babscess\b", "def": "a pocket of pus"},



def _infer_concern(text: str, language: str) -> str:            for number in numbers:    {"pat": r"\bgranuloma\b", "def": "a small area of inflammation"},

    for keyword in ["obstruction", "blockage", "compression", "fracture", "aneurysm", "embol"]:

        if re.search(rf"(?i)\b{keyword}\b", text):                try:    {"pat": r"\bpolyp\b", "def": "a growth projecting from a mucous membrane"},

            sentence = "Please talk to your doctor about the next steps."

            return _maybe_translate_sentence(sentence, language)                    value = float(number)]

    return ""

                except ValueError:_TERM_REGEX: List[Tuple[re.Pattern, str]] = [(re.compile(d["pat"], re.I), d["def"]) for d in _TERM_DEFS]



def _preclean(raw: str) -> str:                    converted.append(number)

    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")

    text = re.sub(r"-\s*\n(?=\w)", "", text)                    continue# ---------- noise ----------

    lines = [line.strip() for line in text.split("\n")]

    drop_line = re.compile(r"(?i)^(name|age|sex|dob|mrn|id|account|ref|patient)\s*[:#]")                if value >= 10:NOISE_PATTERNS = [

    kept = [line for line in lines if line and not drop_line.search(line)]

    cleaned: List[str] = []                    converted.append(f"{round(value / 10.0, 1):g}")    r"\baxial\b", r"\bNECT\b", r"\bCECT\b", r"\bbrain window\b",

    for line in kept:

        if not cleaned or cleaned[-1] != line:                else:    r"\bimages?\s+are\s+viewed", r"\bappear\s+normal\b", r"\bare\s+normal\b",

            cleaned.append(line)

    return "\n".join(cleaned)                    converted.append(f"{round(value, 1):g} mm")    r"\bno\s+abnormalit(y|ies)\b", r"\bnormally\s+developed\b",



            if all("mm" not in item for item in converted):    r"\bparanasal\s+sinuses.*(clear|pneumatiz)", r"\bvisuali[sz]ed\s+lower\s+thorax\s+is\s+normal",

def build_structured(

    text: str,                return " x ".join(converted) + " cm"    r"^\s*(conclusion|impression|summary)\s*:\s*",

    lay_gloss: Glossary | None = None,

    language: str = "English",            return " x ".join(converted)]

    render_style: str = "bullets",

) -> Dict[str, str]:        for number in numbers:NOISE_RX = re.compile("|".join(f"(?:{p})" for p in NOISE_PATTERNS), re.I | re.M)

    _ = render_style  # reserved for future styles

            converted.append(_round_number(number))

    raw_text = text or ""

    if not raw_text.strip():        return " x ".join(converted) + " cm"# ---------- PHI redaction ----------

        return {

            "reason": _maybe_translate_sentence("Reason not provided.", language),_PHI_STOPWORDS = {

            "technique": _maybe_translate_sentence("Technique not described.", language),

            "comparison": "None",    def convert_single(match: re.Match) -> str:    "hospital","clinic","centre","center","medical","radiology","imaging","ct","mri","xray",

            "oral_contrast": "Not stated",

            "findings": _render_bullets([], include_normal=True, language=language),        value = float(match.group(1))    "scan","study","male","female","sex","age","date","mrn","patient","ref","no","number",

            "conclusion": _render_bullets([], include_normal=False, language=language),

            "concern": "",        unit = match.group(2).lower()    "id","account","acct","doctor","dr","clinic",

            "patient": {},

            "word_count": 0,        if unit == "mm" and value >= 10:}

            "sentence_count": 0,

            "highlights_positive": 0,            return f"{round(value / 10.0, 1):g} cm"

            "highlights_negative": 0,

        }        if unit == "cm" and value < 0.1:_PHI_PLACEHOLDER_REPLACEMENTS = {



    cleaned = _preclean(raw_text)            return f"{round(value * 10.0, 1):g} mm"    "[REDACTED]": "the patient",

    metadata_raw = parse_metadata(raw_text)

    metadata = ReportMetadata(        return f"{_round_number(match.group(1))} {unit}"    "[DOB]": "date withheld",

        name=metadata_raw.get("name", ""),

        age=metadata_raw.get("age", ""),    "[AGE]": "age withheld",

        sex=metadata_raw.get("sex", ""),

        hospital=metadata_raw.get("hospital", ""),    text = _MEASUREMENT_BLOCK.sub(convert_block, text or "")    "[SEX]": "sex withheld",

        date=metadata_raw.get("date", ""),

        study=metadata_raw.get("study", ""),    return _SINGLE_MEASUREMENT.sub(convert_single, text)    "[AGE/SEX]": "age/sex withheld",

    )

}

    history_matches = re.findall(r"(?im)^\s*(?:clinical\s*history|history|indication)\s*:\s*([^\n]+)", cleaned)

    metadata.history = "; ".join(dict.fromkeys(match.strip() for match in history_matches if match.strip()))



    sections_raw = sections_from_text(cleaned)_JARGON_MAP = [

    sections = ReportSections(

        reason=sections_raw.get("reason", ""),    (re.compile(r"\bheterogene(?:ous|ity)\b", re.I), "mixed in appearance"),def _phi_term_variants(value: str) -> List[str]:

        technique=sections_raw.get("technique", ""),

        findings=sections_raw.get("findings", ""),    (re.compile(r"\bhypoattenuating\b", re.I), "darker on the scan"),    terms: List[str] = []

        impression=sections_raw.get("impression", ""),

        raw_text=cleaned,    (re.compile(r"\bhyperattenuating\b", re.I), "brighter on the scan"),    val = (value or "").strip()

    )

    (re.compile(r"\bhyperintense\b", re.I), "brighter on the scan"),    if not val:

    phi_terms = _collect_phi_terms(metadata)

    sanitized_for_model = _redact_phi(cleaned, phi_terms)    (re.compile(r"\bhypointense\b", re.I), "darker on the scan"),        return terms

    sanitized_for_public = _normalise_placeholders(sanitized_for_model)

    (re.compile(r"\blesion\b", re.I), "abnormal area"),    cleaned = re.sub(r"\s+", " ", val)

    try:

        min_latency = max(0, int(os.getenv("OPENAI_MIN_LATENCY_MS", "0")))    (re.compile(r"\bmass\b", re.I), "mass"),  # keep word but normalise case    if cleaned:

        if min_latency:

            time.sleep(min(10.0, min_latency / 1000.0))    (re.compile(r"\badenopathy\b", re.I), "swollen lymph nodes"),        terms.append(cleaned)

    except Exception:

        pass    (re.compile(r"\bdilat(?:ation|ed)\b", re.I), "widened"),    split_src = re.sub(r"[:;,_-]+", " ", cleaned)



    llm_summary = _call_openai(sanitized_for_model, language) or {}    (re.compile(r"\bstenosis\b", re.I), "narrowing"),    for piece in split_src.split():

    summary = {key: (llm_summary.get(key) or "").strip() for key in _JSON_KEYS}

    (re.compile(r"\bobstruction\b", re.I), "blockage"),        piece = piece.strip()

    def polish(block: str) -> str:

        block = block or ""    (re.compile(r"\bperi[-\s]?lesional\b", re.I), "around the abnormal area"),        if len(piece) < 2:

        if lay_gloss:

            block = lay_gloss.replace_terms(block)    (re.compile(r"\bextra[-\s]?axial\b", re.I), "outside the brain tissue"),            continue

        sentences = _split_sentences(block)

        if sentences:]        low = piece.lower()

            return " ".join(_simplify_sentence(sentence) for sentence in sentences)

        return _simplify_sentence(block)        if low in _PHI_STOPWORDS:



    reason_text = summary.get("reason") or _infer_reason(sanitized_for_public, sections, metadata, language)_SENTENCE_SWAPS = [            continue

    technique_text = summary.get("technique") or _infer_technique(sanitized_for_public, sections, language)

    (re.compile(r"\bthere\s+is\s+([a-z][^,]+),\s*(which|that)\s+"), lambda m: f"{m.group(1).capitalize()} {m.group(2)} "),        if not re.search(r"[A-Za-z]", piece):

    findings_items = _split_sentences(summary.get("findings", "")) or _extract_key_findings(sections)

    conclusion_items = _split_sentences(summary.get("conclusion", "")) or _extract_conclusion(sections)    (re.compile(r"\bis\s+noted\b", re.I), ""),            continue



    concern_text = summary.get("concern") or _infer_concern(sanitized_for_public, language)    (re.compile(r"\bis\s+seen\b", re.I), ""),        terms.append(piece)



    reason_text = polish(reason_text)    (re.compile(r"\s+\.", re.I), "."),    return terms

    technique_text = polish(technique_text)

    concern_text = polish(concern_text) if concern_text else ""]



    findings_html = _render_bullets(findings_items, include_normal=True, language=language)

    conclusion_html = _render_bullets(conclusion_items, include_normal=False, language=language)

_TERMINOLOGY_REWRITE = {def _collect_phi_terms(meta: Dict[str, str]) -> List[str]:

    comparison_match = re.search(r"(?im)^\s*comparison\s*:\s*(.+)$", sanitized_for_public)

    oral_match = re.search(r"(?im)^\s*oral\s+contrast\s*:\s*(.+)$", sanitized_for_public)    "unremarkable": "looks normal",    terms: List[str] = []



    words = len(re.findall(r"\w+", sanitized_for_public))    "intact": "normal",    for key in ("name", "hospital", "date"):

    sentences = len(_split_sentences(sanitized_for_public))

    pos_hits = len(re.findall(r'class="ii-pos"', findings_html + conclusion_html))    "benign": "not dangerous",        val = meta.get(key, "")

    neg_hits = len(re.findall(r'class="ii-neg"', findings_html + conclusion_html))

    "symmetric": "the same on both sides",        terms.extend(_phi_term_variants(val))

    patient_bundle = {

        "name": metadata.name,    "heterogenous": "mixed in appearance",    return [t for t in terms if t]

        "age": metadata.age,

        "sex": metadata.sex,    "hyperdense": "brighter on the scan",

        "hospital": metadata.hospital,

        "date": metadata.date,    "hypodense": "darker on the scan",

        "study": metadata.study,

        "history": metadata.history,    "enhancing": "lighting up after dye",def _normalize_phi_placeholders(text: str) -> str:

    }

}    t = text or ""

    def wrap_text(value: str) -> str:

        value = value.strip()    for placeholder, replacement in _PHI_PLACEHOLDER_REPLACEMENTS.items():

        if not value:

            return ""        if placeholder in t:

        value = _maybe_translate_sentence(value, language)

        return f'<span class="ii-text" style="color:#ffffff">{value}</span>'def _simplify_sentence(text: str) -> str:            t = t.replace(placeholder, replacement)



    return {    sentence = text or ""    return t

        "reason": wrap_text(reason_text),

        "technique": wrap_text(technique_text),    if not sentence:

        "comparison": comparison_match.group(1).strip() if comparison_match else "None",

        "oral_contrast": oral_match.group(1).strip() if oral_match else "Not stated",        return ""

        "findings": findings_html,

        "conclusion": conclusion_html,    sentence = _convert_measurements(sentence)def _redact_phi(s: str, extra_terms: List[str] | None = None) -> str:

        "concern": wrap_text(concern_text) if concern_text else "",

        "word_count": words,    for search, replace in _JARGON_MAP:    t = s or ""

        "sentence_count": sentences,

        "highlights_positive": pos_hits,        sentence = search.sub(replace, sentence)    t = re.sub(r"(?im)^\s*(name|patient|pt|mrn|id|acct|account|gender|sex|age|dob|date\s+of\s+birth)\s*[:#].*$","[REDACTED]",t)

        "highlights_negative": neg_hits,

        "patient": patient_bundle,    for search, replace in _SENTENCE_SWAPS:    t = re.sub(r"(?i)\bDOB\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","[DOB]",t)

    }

        sentence = search.sub(replace if isinstance(replace, str) else replace, sentence)    t = re.sub(r"(?i)\b(date\s+of\s+birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","[DOB]",t)



__all__ = ["Glossary", "build_structured"]    for key, value in _TERMINOLOGY_REWRITE.items():    t = re.sub(r"(?i)\b(\d{1,3})\s*(?:year[- ]?old|y/o|yo|yrs?|years?)\b","[AGE]",t)


        sentence = re.sub(rf"(?i)\b{re.escape(key)}\b", value, sentence)    t = re.sub(r"(?i)\b(?:male|female)\b","[SEX]",t)

    sentence = re.sub(r"\s{2,}", " ", sentence)    t = re.sub(r"(?i)\b(\d{1,3})\s*/\s*(m|f)\b","[AGE/SEX]",t)

    sentence = sentence.replace(" ,", ",").replace(" .", ".")    t = re.sub(r"(?i)\b(\d{1,3})(m|f)\b","[AGE/SEX]",t)

    sentence = sentence.strip()    t = re.sub(r"(?im)^(\s*(indication|reason|history)\s*:\s*)[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){0,2},\s*",r"\1",t)

    if sentence and not sentence[0].isupper():    if extra_terms:

        sentence = sentence[0].upper() + sentence[1:]        for term in extra_terms:

    return sentence            term = (term or "").strip()

            if not term or len(term) < 2:

                continue

def _split_sentences(text: str) -> List[str]:            escaped = re.escape(term)

    norm = re.sub(r"\s+", " ", text or "").strip()            t = re.sub(rf"(?i){escaped}", "[REDACTED]", t)

    if not norm:    return t

        return []

    parts = re.split(r"(?<=[.!?])\s+", norm)# ---------- helpers ----------

    return [part.strip() for part in parts if part.strip()]def _normalize_listish(text: str) -> List[str]:

    t = (text or "").strip()

    # JSON array

# ---------------------------------------------------------------------------    try:

# Tooltip + highlighting helpers (ported / cleaned up from previous pipeline)        val = json.loads(t)

# ---------------------------------------------------------------------------        if isinstance(val, list):

_NEGATIVE_TERMS = {            return [re.sub(r"^\s*[\-\*\u2022]\s*", "", str(x or "").strip()) for x in val if str(x or "").strip()]

    "mass": "an abnormal lump that can press on tissue",    except Exception:

    "lesion": "an abnormal area",        pass

    "tumor": "a growth that forms a lump",    # Python literal list: ['a', 'b']

    "tumour": "a growth that forms a lump",    try:

    "cancer": "a harmful growth that can spread",        if re.match(r"^\s*\[.*\]\s*$", t, flags=re.S):

    "obstruction": "a blockage",            val = ast.literal_eval(t)

    "blockage": "a blockage",            if isinstance(val, list):

    "stenosis": "narrowing of a passage",                return [re.sub(r"^\s*[\-\*\u2022]\s*", "", str(x or "").strip()) for x in val if str(x or "").strip()]

    "fracture": "a broken bone",    except Exception:

    "hemorrhage": "bleeding",        pass

    "haemorrhage": "bleeding",    # Bullet lines

    "edema": "swelling with fluid buildup",    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

    "dilation": "widening",    bullets = [re.sub(r"^\s*[\-\*\u2022]\s*", "", ln) for ln in lines if re.match(r"^\s*[\-\*\u2022]", ln)]

    "dilatation": "widening",    if bullets:

}        return bullets

    # Semicolon list

_NEGATIVE_PATTERNS = [re.compile(rf"(?i)\b{term}\b") for term in _NEGATIVE_TERMS]    if ";" in t and not re.search(r"[.!?]\s*$", t):

_POSITIVE_PATTERN = re.compile(r"(?i)\b(no\s+evidence\b|no\s+significant|normal|benign|without)\b")        parts = [p.strip() for p in t.split(";") if p.strip()]

        if len(parts) > 1:

            return parts

def _wrap_pos(text: str) -> str:    return []

    return f'<span class="ii-pos" style="color:#22c55e;font-weight:600">{text}</span>'

def _split_sentences(s: str) -> List[str]:

    t = re.sub(r"\s+", " ", s or "").strip()

def _wrap_neg(term: str, definition: str = "") -> str:    return re.split(r"(?<=[.!?])\s+", t) if t else []

    data = f' data-def="{definition.replace("\"", "&quot;")}"' if definition else ""

    return f'<span class="ii-neg" style="color:#ef4444;font-weight:600"{data}>{term}</span>'def _round_number_token(tok: str) -> str:

    try:

        f = float(tok); return str(int(round(f))) if abs(f) >= 10 else f"{round(f,1):g}"

def _highlight_sentence(text: str) -> str:    except Exception:

    if not text:        return tok

        return ""

    output = textdef _convert_units(s: str) -> str:

    for pattern in _NEGATIVE_PATTERNS:    def conv_dim(m: re.Match) -> str:

        def repl(match: re.Match) -> str:        nums = re.split(r"\s*[x×]\s*", m.group(1)); unit = m.group(2).lower(); out: List[str] = []

            token = match.group(0)        if unit == "mm":

            definition = _NEGATIVE_TERMS.get(token.lower(), "")            for t in nums:

            return _wrap_neg(token, definition)                try:

                    val = float(t); out.append(f"{round(val/10.0,1):g}" if val>=10 else f"{round(val,1):g} mm")

        output = pattern.sub(repl, output)                except Exception: out.append(t)

    output = _POSITIVE_PATTERN.sub(lambda m: _wrap_pos(m.group(0)), output)            return (" x ".join(out) + (" cm" if all(not x.endswith("mm") for x in out) else ""))

    return f'<span class="ii-text" style="color:#ffffff">{output}</span>'        if unit == "cm":

            for t in nums: out.append(_round_number_token(t))

            return " x ".join(out) + " cm"

def _render_bullets(items: List[str], include_normal: bool, language: str) -> str:        return m.group(0)

    cleaned: List[str] = []    s = re.sub(r"((?:\d+(?:\.\d+)?)(?:\s*[x×]\s*(?:\d+(?:\.\d+)?)){1,3})\s*(mm|cm)\b", conv_dim, s)

    for sentence in items:    def conv_single(m: re.Match) -> str:

        simplified = _simplify_sentence(sentence)        val = float(m.group(1)); unit = m.group(2).lower()

        if not simplified:        if unit=="mm" and val>=10: return f"{round(val/10.0,1):g} cm"

            continue        if unit=="cm" and val<0.1:  return f"{round(val*10.0,1):g} mm"

        cleaned.append(_highlight_sentence(simplified))        return f"{_round_number_token(m.group(1))} {unit}"

    if include_normal:    return re.sub(r"\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", conv_single, s)

        normal = "Most other areas look normal." if language.lower() not in ("kiswahili", "swahili") else "Maeneo mengine yanaonekana kawaida."

        cleaned.append(_highlight_sentence(normal))def _numbers_simple(text_only: str) -> str:

    if not cleaned:    s = text_only or ""

        fallback = "No major problems were seen." if language.lower() not in ("kiswahili", "swahili") else "Hakuna matatizo makubwa yaliyoonekana."    s = _convert_units(s)

        cleaned.append(_highlight_sentence(fallback))    s = re.sub(r"(?<!\w)(\d+\.\d+|\d+)(?!\w)", lambda m: _round_number_token(m.group(0)), s)

    return "<ul class='ii-list' style='color:#ffffff'>" + "".join(f"<li>{item}</li>" for item in cleaned[:5]) + "</ul>"    return re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " x ", s)



def _grammar_cleanup(s: str) -> str:

# ---------------------------------------------------------------------------    s = re.sub(r"\bare looks\b", "look", s or "", flags=re.I)

# Kiswahili support for fallback phrases    s = re.sub(r"\bis looks\b", "looks", s, flags=re.I)

# ---------------------------------------------------------------------------    s = re.sub(r"\bare appears?\b", "appear", s, flags=re.I)

_KISWAHILI_FALLBACKS = {    s = re.sub(r"\bis appear\b", "appears", s, flags=re.I)

    "Technique not described.": "Mbinu haijaelezewa.",    s = re.sub(r"\bis\s+noted\b", "", s, flags=re.I)

    "Please talk to your doctor about the next steps.": "Tafadhali zungumza na daktari wako kuhusu hatua zinazofuata.",    s = re.sub(r"\bis\s+seen\b", "", s, flags=re.I)

    "Most other areas look normal.": "Maeneo mengine yanaonekana kawaida.",    s = re.sub(r"\s+\.", ".", s); s = re.sub(r"\s+,", ",", s); s = re.sub(r"\s{2,}", " ", s)

    "No major problems were seen.": "Hakuna matatizo makubwa yaliyoonekana.",    return s.strip()

}

def _fix_swelling_phrasing(s: str) -> str:

    t = s or ""

def _maybe_translate_sentence(sentence: str, language: str) -> str:    # "There is swelling in X" -> "Swelling in X"

    if language.lower() not in ("kiswahili", "swahili"):    t = re.sub(r"(?i)\bthere\s+(?:is|was|are)\s+swelling\s+in\s+([a-z][a-z\s\-]{2,})",

        return sentence               lambda m: f"Swelling in {m.group(1).strip()}", t)

    return _KISWAHILI_FALLBACKS.get(sentence, sentence)    # "swelling of X" -> "Swelling in X"

    t = re.sub(r"(?i)\bswelling\s+of\s+([a-z][a-z\s\-]{2,})",

               lambda m: f"Swelling in {m.group(1).strip()}", t)

# ---------------------------------------------------------------------------    # "X swelling" -> "Swelling in X"

# LLM client    t = re.sub(r"\b([A-Za-z][A-Za-z\s\-]{3,})\s+swelling\b",

# ---------------------------------------------------------------------------               lambda m: f"Swelling in {m.group(1).strip()}", t)

_JSON_KEYS = ["reason", "technique", "findings", "conclusion", "concern"]    # Cleanup double inserts

    t = re.sub(r"(?i)\bSwelling in\s+(there\s+(?:is|are)\s+)", "Swelling in ", t)

    return t

def _resolve_models() -> Tuple[str, str]:

    env_model = os.getenv("OPENAI_MODEL", "gpt-5")_PHRASE_TIDY = [

    fallback = os.getenv("OPENAI_CHAT_FALLBACK", "gpt-4o-mini")    (re.compile(r"\bRight\s+fronto\s*parietal\b", re.I), "Right frontoparietal"),

    return env_model, fallback    (re.compile(r"\bFronto\s*parietal\b", re.I), "frontoparietal"),

    (re.compile(r"\boutside the brain tissue\s+enhances with contrast dye\s+(tumou?r)\b", re.I), r"\1 outside the brain tissue that enhances with contrast dye"),

    (re.compile(r"\benhances with contrast dye\s+(tumou?r)\b", re.I), r"\1 that enhances with contrast dye"),

def _supports_chat(model: str) -> bool:    (re.compile(r"\boutside the brain tissue\s+(tumou?r)\b", re.I), r"\1 outside the brain tissue"),

    lower = (model or "").lower()]

    return any(token in lower for token in ["gpt-4", "gpt-4o", "4o-mini", "gpt-3.5", "mini", "o1"])def _tidy_phrases(s: str) -> str:

    out = s or ""

    for rx, repl in _PHRASE_TIDY: out = rx.sub(repl, out)

def _call_openai(text: str, language: str) -> Dict[str, str] | None:    return out

    from openai import OpenAI

def _dedupe_redundant_noun_phrase(s: str) -> str:

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))    """Within each sentence, replace 'may/might be a(n) X' with 'is indeterminate'

    env_model, chat_fallback = _resolve_models()    only when X already appears earlier in that same sentence."""

    nouns = ["mass", "lesion", "tumor", "tumour", "cyst", "nodule", "polyp"]

    if language.lower() in ("kiswahili", "swahili"):    out_sents: List[str] = []

        instructions = """Wewe ni msaidizi wa kuandika ripoti za uchunguzi wa mwili kwa lugha rahisi. Andika KILA KITU kwa Kiswahili sanifu bila kuchanganya Kiingereza.    for sent in _split_sentences(s or ""):

Rudisha tu JSON iliyo na funguo: reason, technique, findings, conclusion, concern.        t = sent

Tumia sentensi fupi, zenye maneno 8-12. Eleza maneno ya kitabibu kwa lugha rahisi (weka ufafanuzi kwenye mabano ikiwa ni lazima).        for n in nouns:

"""            # if noun appears earlier in the sentence

    else:            if re.search(rf"(?i)\b{re.escape(n)}\b", t):

        instructions = """You summarise medical imaging reports for patients. Return ONLY JSON with keys reason, technique, findings, conclusion, concern.                # replace trailing hedge about same noun

Use clear, compassionate language. Explain medical jargon in parentheses. Keep numbers exactly as provided.                t = re.sub(

"""                    rf"(?i)\b(?:may|might)\s+be\s+a?n?\s+{re.escape(n)}\b",

                    "is indeterminate",

    payload = {                    t,

        "role": "system",                )

        "content": instructions.strip() + "\n\nReport:\n" + text.strip(),        out_sents.append(t)

    }    return " ".join(out_sents)



    try:

        if _supports_chat(env_model):def _strip_signatures(s: str) -> str:

            response = client.chat.completions.create(    s = re.sub(r"(?im)^\s*(dr\.?.*|consultant\s*radiologist.*|radiologist.*|dictated\s+by.*)\s*$","",s or "")

                model=env_model,    s = re.sub(r"(?im)^\s*(signed|electronically\s+signed.*)\s*$","",s); return s.strip()

                temperature=0.2,

                messages=[payload, {"role": "user", "content": "Summarise the report as instructed."}],def _unwrap_soft_breaks(s: str) -> str:

                response_format={"type": "json_object"},    s = (s or "").replace("\r\n","\n").replace("\r","\n")

                timeout=90,    s = re.sub(r"-\s*\n(?=\w)","",s); s = re.sub(r"[ \t]+\n","\n",s); s = re.sub(r"\n[ \t]+","\n",s)

            )    s = re.sub(r"(?<!\n)\n(?!\n)"," ",s)

            return json.loads(response.choices[0].message.content or "{}")    return re.sub(r"\n{3,}","\n\n",s)

        # fall back to responses API with JSON object

        resp = client.responses.create(def _is_caps_banner(ln: str) -> bool:

            model=env_model,    if not ln or len(ln) < 8: return False

            input=[    letters = re.sub(r"[^A-Za-z]","",ln)

                {    if not letters: return False

                    "role": "system",    upper_ratio = sum(c.isupper() for c in letters) / max(1,len(letters))

                    "content": instructions.strip(),    tokens = len(ln.split())

                },    has_modality = bool(re.search(r"\b(MRI|CT|US|XR)\b", ln))

                {    return (upper_ratio >= 0.85 and tokens >= 8 and not has_modality)

                    "role": "user",

                    "content": text.strip(),def _preclean_report(raw: str) -> str:

                },    if not raw: return ""

            ],    s = _unwrap_soft_breaks(raw)

            response_format={"type": "json_object"},    lines = [ln.strip() for ln in s.split("\n")]

            temperature=0.2,    start_rx = re.compile(r"(?i)\b(history|indication|reason|technique|procedure|findings?|impression|conclusion|report|scan|mri|ct|ultrasound|usg|axial|cect|nect)\b")

            timeout=90,    drop_exact = re.compile(r"(?i)^(report|summary|x-?ray|ct\s+head|ct\s+brain)$")

        )    drop_keyval = re.compile(r"(?i)^\s*(ref(\.|:)?\s*no|ref|date|name|age|sex|gender|mrn|id|file|account|acct|dob|date\s+of\s+birth)\s*[:#].*$")

        output = resp.output[0].content[0].text if resp.output else "{}"    start = 0

        return json.loads(output or "{}")    for i, ln in enumerate(lines):

    except BadRequestError as exc:        if start_rx.search(ln):

        # Retry with fallback model if JSON mode unsupported            start = i; break

        if chat_fallback and chat_fallback != env_model and "json" in (exc.message or "").lower():    kept: List[str] = []

            try:    for ln in lines[start:]:

                response = client.chat.completions.create(        if not ln or drop_exact.match(ln) or drop_keyval.match(ln) or _is_caps_banner(ln):

                    model=chat_fallback,            continue

                    temperature=0.2,        kept.append(ln)

                    messages=[payload, {"role": "user", "content": "Summarise the report as instructed."}],    cleaned: List[str] = []

                    response_format={"type": "json_object"},    for ln in kept:

                    timeout=90,        if not cleaned or cleaned[-1] != ln: cleaned.append(ln)

                )    return "\n".join(cleaned)

                return json.loads(response.choices[0].message.content or "{}")

            except Exception:def _extract_history(cleaned: str) -> Tuple[str, str]:

                logger.exception("fallback chat completion failed")    pattern = re.compile(r"(?im)^\s*(?:clinical\s*(?:hx|history)|history|indication)\s*:\s*([^\n.]+)\.?\s*$")

        logger.exception("OpenAI request failed (BadRequest)")    outs = [m.group(1).strip() for m in pattern.finditer(cleaned or "")]

    except NotFoundError:    text_wo = pattern.sub("", cleaned or "")

        logger.exception("OpenAI model not found")    return ("; ".join(dict.fromkeys(outs)).strip(), text_wo)

    except Exception:

        logger.exception("Unexpected OpenAI failure")def _strip_labels(s: str) -> str:

    return None    s = s or ""

    s = re.sub(r"(?im)^\s*(reason|indication|procedure|technique|findings?|impression|conclusion|summary|ddx)\s*:\s*", "", s)

    return re.sub(r"(?i)\b(findings?|impression|conclusion|summary|ddx)\s*:\s*", "", s).strip()

# ---------------------------------------------------------------------------

# Heuristic fallbacksdef _simplify(text: str, gloss: Glossary | None) -> str:

# ---------------------------------------------------------------------------    s = text or ""

_REASON_PATTERNS = re.compile(r"(?im)^\s*(indication|reason|history|clinical\s+history)\s*:\s*(.+)$")    if gloss: s = gloss.replace_terms(s)

    s = re.sub(r"\bcm\b"," centimeters",s,flags=re.I); s = re.sub(r"\bmm\b"," millimeters",s,flags=re.I)

    s = re.sub(r"\bHU\b"," Hounsfield units",s,flags=re.I)

def _infer_reason(text: str, sections: ReportSections, metadata: ReportMetadata, language: str) -> str:    s = re.sub(r"\bunremarkable\b","looks normal",s,flags=re.I)

    if sections.reason:    s = re.sub(r"\bintact\b","normal",s,flags=re.I)

        raw = re.sub(r"(?im)^\s*(indication|reason|history|clinical\s+history)\s*:\s*", "", sections.reason).strip()    s = re.sub(r"\bsymmetric\b","same on both sides",s,flags=re.I)

        if raw and len(raw.split()) <= 18:    s = re.sub(r"\bbenign\b","not dangerous",s,flags=re.I)

            sentence = raw if raw.endswith(".") else raw + "."    s = _rewrite_jargon(s); s = _numbers_simple(s); s = _fix_swelling_phrasing(s); s = _grammar_cleanup(s); s = _tidy_phrases(s)

            if not re.match(r"(?i)^(the|this|patient)", sentence.strip()):    return s.strip()

                sentence = "The scan was ordered because " + sentence.lstrip().lower()

            return _maybe_translate_sentence(_simplify_sentence(sentence), language)# ---------- tooltip wrappers ----------

    match = _REASON_PATTERNS.search(text or "")def _escape_attr(s: str) -> str:

    if match:    s = s or ""

        reason_text = match.group(2).strip()    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#x27;")

        if len(reason_text) < 10:

            sentence = f"The scan was ordered to evaluate {reason_text.lower()}."def _annotate_terms_onepass(text_only: str) -> str:

        else:    if not text_only: return ""

            sentence = reason_text if reason_text.endswith(".") else reason_text + "."    matches: List[Tuple[int,int,str,str]] = []

        return _maybe_translate_sentence(_simplify_sentence(sentence), language)    for rx, d in _TERM_REGEX:

    default = "The scan was ordered to look for a problem in the area." if language.lower() not in ("kiswahili", "swahili") else "Skani iliagizwa kutafuta tatizo katika eneo hili."        for m in rx.finditer(text_only):

    return default            matches.append((m.start(), m.end(), m.group(0), d))

    if not matches: return text_only

    matches.sort(key=lambda t: (t[0], -(t[1]-t[0])))

def _infer_technique(text: str, sections: ReportSections, language: str) -> str:    kept: List[Tuple[int,int,str,str]] = []; last_end = -1

    technique = sections.technique    for s,e,vis,d in matches:

    if technique:        if s < last_end: continue

        sentences = _split_sentences(technique)        kept.append((s,e,vis,d)); last_end = e

        if sentences:    out: List[str] = []; pos = 0

            joined = " ".join(_simplify_sentence(s) for s in sentences[:4])    for s,e,vis,d in kept:

            return _maybe_translate_sentence(joined, language)        if s > pos: out.append(text_only[pos:s])

    # fallback heuristics        out.append(f'<span class="term-def" data-def="{_escape_attr(d)}">{_escape_attr(vis)}</span>')

    modality = "scan"        pos = e

    if re.search(r"\bmri\b", text, flags=re.I):    out.append(text_only[pos:]); return "".join(out)

        modality = "MRI scan"

    elif re.search(r"\bct\b", text, flags=re.I):def _annotate_terms_outside_tags(htmlish: str) -> str:

        modality = "CT scan"    parts = re.split(r"(<[^>]+>)", htmlish or "")

    elif re.search(r"ultrasound", text, flags=re.I):    for i in range(0,len(parts),2): parts[i] = _annotate_terms_onepass(parts[i])

        modality = "Ultrasound"    return "".join(parts)

    body = metadata.study or "the area of concern"

    base = f"{modality} of {body.lower()} was performed."# ---------- phrase-aware highlighting ----------

    return _maybe_translate_sentence(_simplify_sentence(base), language)_POS_SENTENCE_RX = re.compile(r"(?i)\b(no|none|without|absent|free of|negative for|not seen|no evidence of|no significant)\b")

_NEG_RXES = [re.compile(p, re.I) for p in NEG_PHRASES] + [re.compile(rf"(?i)\b{re.escape(w)}\b") for w in NEG_WORDS]

_POS_RX = re.compile(r"(?i)\b(normal|benign|unremarkable|clear|symmetric|intact|stable|improved)\b")

def _extract_key_findings(sections: ReportSections) -> List[str]:_NO_RX = re.compile(r"(?i)(no\s+(?:[a-z/-]+(?:\s+[a-z/-]+){0,3}))")

    pool = sections.findings or sections.raw_text_WITHOUT_RX = re.compile(r"(?i)(without\s+(?:[a-z/-]+(?:\s+[a-z/-]+){0,3}))")

    pool = re.sub(r"(?im)^\s*(findings?|impression|conclusion|summary)\s*:\s*", "", pool)

    bullets = []def _has_neg_term(s: str) -> bool: return any(rx.search(s) for rx in _NEG_RXES)

    for line in pool.splitlines():def _has_pos_cue(s: str) -> bool: return bool(_POS_SENTENCE_RX.search(s))

        stripped = line.strip()

        if not stripped:def _wrap_green(t: str) -> str: return f'<span class="ii-pos" style="color:#22c55e;font-weight:600">{t}</span>'

            continuedef _wrap_red(tok: str, defn: str = "") -> str:

        if stripped.lower().startswith("impression"):    data = f' data-def="{_escape_attr(defn)}"' if defn else ""

            continue    return f'<span class="ii-neg" style="color:#ef4444;font-weight:600"{data}>{tok}</span>'

        bullets.append(stripped)

    if not bullets:def _highlight_phrasewise(text: str) -> str:

        bullets = _split_sentences(pool)    s = text or ""; low = s.lower()

    return bullets[:6]    if _has_neg_term(low) and _has_pos_cue(low):

        return f'<span class="ii-text" style="color:#ffffff">{_wrap_green(s)}</span>'

    t = s

def _extract_conclusion(sections: ReportSections) -> List[str]:    for rx in _NEG_RXES:

    text = sections.impression or ""        def _neg_repl(m: re.Match) -> str:

    if not text:            tok = m.group(0); key = tok.lower(); defn = NEG_DEFS.get(key, NEG_DEFS.get(key.strip().lower(), ""))

        return []            return _wrap_red(tok, defn)

    sentences = _split_sentences(text)        t = rx.sub(_neg_repl, t)

    return sentences[:3]    t = _NO_RX.sub(lambda m: _wrap_green(m.group(0)), t)

    t = _WITHOUT_RX.sub(lambda m: _wrap_green(m.group(0)), t)

    t = _POS_RX.sub(lambda m: _wrap_green(m.group(0)), t)

def _infer_concern(text: str, language: str) -> str:    return f'<span class="ii-text" style="color:#ffffff">{t}</span>'

    for keyword in ["obstruction", "blockage", "compression", "fracture", "embol", "aneurysm"]:

        if re.search(rf"(?i)\b{keyword}\b", text):# ---------- JSON utils ----------

            sentence = "The findings should be discussed with your doctor to decide the next steps."def _extract_json_loose(s: str) -> Dict[str, str] | None:

            return _maybe_translate_sentence(sentence, language)    if not s: return None

    return ""    try: return json.loads(s)

    except Exception:

        m = re.search(r"\{.*\}", s, flags=re.S)

# ---------------------------------------------------------------------------        if not m: return None

# Public API        try: return json.loads(m.group(0))

# ---------------------------------------------------------------------------        except Exception: return None



def _preclean(raw: str) -> str:# ---------- Model resolution ----------

    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")def _supports_chat_completions(m: str) -> bool:

    text = re.sub(r"-\s*\n(?=\w)", "", text)    m = (m or "").lower()

    lines = [line.strip() for line in text.split("\n")]    return any(p in m for p in ["gpt-4", "gpt-4o", "gpt-4o-mini", "3.5", "mini"])

    drop_line = re.compile(r"(?i)^(name|age|sex|dob|mrn|id|account|ref|patient)\s*[:#]")

    kept: List[str] = []def _is_reasoning_model(m: str) -> bool:

    for line in lines:    m = (m or "").lower()

        if not line:    return any(x in m for x in ["gpt-5", "o3", "o4-mini-high"])

            continue

        if drop_line.search(line):def _resolve_models() -> Tuple[str, str]:

            continue    """Return (env_model, chat_fallback). chat_fallback must support JSON mode."""

        kept.append(line)    env_model = os.getenv("OPENAI_MODEL", "gpt-5")

    cleaned: List[str] = []    chat_fallback = os.getenv("OPENAI_CHAT_FALLBACK", "gpt-4o-mini")

    for line in kept:    return (env_model, chat_fallback)

        if not cleaned or cleaned[-1] != line:

            cleaned.append(line)# ---------- OpenAI ----------

    return "\n".join(cleaned)def _call_openai_once(report_text: str, language: str, temperature: float, effort: str) -> Dict[str, str] | None:

    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def build_structured(    env_model, chat_fallback = _resolve_models()

    text: str,

    lay_gloss: Glossary | None = None,    # Language-specific instructions

    language: str = "English",    if language.lower() in ["kiswahili", "swahili"]:

    render_style: str = "bullets",        instructions = f"""Wewe ni msaidizi wa kuandika ripoti za uchunguzi wa mwili kwa lugha rahisi. Andika KILA KITU kwa Kiswahili sanifu BILA kuchanganya Kiingereza.

) -> Dict[str, str]:Rudisha JSON object tu yenye: reason, technique, findings, conclusion, concern.

    _ = render_style  # reserved for future variantsHadhira ni mtoto wa miaka 10. Tumia sentensi FUPI SANA (maneno 5-8 kwa kila sentensi). Tumia maneno ya kawaida ambayo mtoto anaweza kuelewa.



    raw_text = text or ""reason: Eleza KWA NINI uchunguzi ulifanywa (sentensi 1-2 FUPI SANA). Jumuisha dalili za mgonjwa kwa maneno rahisi. Mfano: "Uchunguzi uliagizwa kwa sababu mgonjwa alikuwa na maumivu ya kichwa na kizunguzungu kwa wiki 2."

    if not raw_text.strip():

        return {technique: Eleza JINSI uchunguzi ulivyofanywa (sentensi 3-5) kwa lugha rahisi. Jumuisha:

            "reason": _maybe_translate_sentence("Reason not provided.", language),- Aina gani ya uchunguzi (MRI, CT, X-ray, Ultrasound)

            "technique": _maybe_translate_sentence("Technique not described.", language),- Sehemu gani ya mwili ilipigiwa picha

            "comparison": "None",- Jinsi picha zilivyochukuliwa (eleza 'axial' = vipande vya kukata kama mkate, 'coronal' = vipande vya mbele-hadi-nyuma, 'sagittal' = vipande vya upande-hadi-upande)

            "oral_contrast": "Not stated",- Kama dawa ya rangi ilitumiwa na kwa nini ('pamoja na rangi' = dawa maalum ilidukuliwa ili kuona viungo vizuri zaidi, 'bila rangi' = hakuna dawa ilihitajika)

            "findings": _render_bullets([], include_normal=True, language=language),- Eneo gani lilipimwa ('kutoka msingi wa fuvu hadi juu' = kutoka chini ya kichwa hadi juu)

            "conclusion": _render_bullets([], include_normal=False, language=language),Mfano: "Uchunguzi wa MRI wa ubongo ulifanywa. Picha za kukata zilichukuliwa kama kukata mkate. Hakuna dawa ya rangi iliyodukuliwa. Kichwa chote kilipimwa kutoka chini hadi juu."

            "concern": "",

            "patient": {},findings: bullets 2-3 FUPI; conclusion: bullets 1-2 FUPI; concern: sentensi 1 FUPI.

            "word_count": 0,WEKA NAMBA ZOTE kama zilivyo katika ripoti ya asili - USIZIPUNGUZE. Kama ripoti inasema "5.4 x 5.6 x 6.7 cm", weka sawa sawa kama hivo. Kagua tahajia YOTE. Usitumie majina ya kitaalamu au maneno ya kisayansi.

            "sentence_count": 0,Andika KILA KITU kwa Kiswahili sanifu bila Kiingereza:

            "highlights_positive": 0,- "scan" → "uchunguzi" au "skani"

            "highlights_negative": 0,- "mass" → "uvimbe" au "chungu"

        }- "normal" → "kawaida"

- "abnormal" → "si kawaida"

    cleaned = _preclean(raw_text)- "brain" → "ubongo"

    parsed_meta = parse_metadata(raw_text)- "liver" → "ini"

    metadata = ReportMetadata(- "kidney" → "figo"

        name=parsed_meta.get("name", ""),- "fracture" → "mfupa umevunjika"

        age=parsed_meta.get("age", ""),Hakikisha KILA neno ni Kiswahili."""

        sex=parsed_meta.get("sex", ""),    else:

        hospital=parsed_meta.get("hospital", ""),        instructions = f"""You summarize medical imaging reports for the public. Write ALL output EXCLUSIVELY in {language} - do not mix languages.

        date=parsed_meta.get("date", ""),Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.

        study=parsed_meta.get("study", ""),Audience: educated adult who is not a medical professional. Use clear, conversational language. Avoid patronizing tone.

    )

CRITICAL: Extract information from the ACTUAL report provided - DO NOT copy these examples. These are templates showing the style only:

    history_matches = re.findall(r"(?im)^\s*(?:clinical\s*history|history|indication)\s*:\s*([^\n]+)", cleaned)

    metadata.history = "; ".join(dict.fromkeys(m.strip() for m in history_matches if m.strip()))reason: Explain WHY the scan was ordered in 2-3 sentences. Extract from the "Clinical History", "Indication", or "Reason" section of the report. Connect to the patient's actual symptoms/clinical history mentioned in THIS specific report. Be specific and empathetic.

Example STYLE (adapt to actual report): "This MRI scan was ordered to investigate lower back pain that the patient has been experiencing. The goal was to examine the lumbar spine and identify any structural issues causing discomfort."

    sections_dict = sections_from_text(cleaned)

    sections = ReportSections(technique: Explain HOW the scan was performed in 4-6 sentences. Extract from the "Technique", "Procedure", or technical details section. Use analogies where helpful but don't oversimplify. Include:

        reason=sections_dict.get("reason", ""),- What imaging technology was ACTUALLY used according to the report (MRI, CT, X-ray, ultrasound, etc.) and what makes it special

        technique=sections_dict.get("technique", ""),- Which body region was ACTUALLY examined according to the report

        findings=sections_dict.get("findings", ""),- Whether contrast was ACTUALLY used according to the report

        impression=sections_dict.get("impression", ""),- What the technology can reveal that physical examination cannot

        raw_text=cleaned,Example STYLE (adapt to actual report): "An MRI (Magnetic Resonance Imaging) scan of the lumbar spine was performed using a 0.35 Tesla magnet. This technology uses powerful magnetic fields and radio waves to create detailed cross-sectional images of soft tissues, discs, and nerves. The imaging captured the spine from multiple angles—top-down (axial), side-to-side (sagittal), and front-to-back (coronal)—to build a complete 3D picture. No contrast dye was needed because the natural differences in tissue density provided clear images. This type of scan is especially good at showing disc problems, nerve compression, and spinal canal narrowing that wouldn't be visible on a regular X-ray."

    )

findings: Present 3-5 key findings from the ACTUAL report in clear bullet points. Start with NORMAL findings to provide context, then address abnormalities. Translate complex medical language into simple, clear sentences. Each bullet should be ONE complete sentence.

    phi_terms = _collect_phi_terms(metadata)CRITICAL for findings:

    sanitized_for_model = _redact_phi(cleaned, phi_terms)- Simplify complex medical jargon: "hypo-attenuating mass lesion" → "a darker area that appears to be a mass"

    sanitized_for_public = _normalise_placeholders(sanitized_for_model)- Remove redundant phrases: "noted in the head the patient the pancreas" → "in the head of the pancreas"

- Each bullet point should be clear and standalone - avoid fragments

    try:- Start with normal/reassuring findings, then abnormalities

        min_latency = max(0, int(os.getenv("OPENAI_MIN_LATENCY_MS", "0")))- Use measurements exactly as stated but explain what they mean

        if min_latency:Example STYLE format (use actual findings from the report):

            time.sleep(min(10.0, min_latency / 1000.0))- "Most of the surrounding organs look healthy: the liver, spleen, and kidneys all appear normal."

    except Exception:- "The pancreas shows a mass measuring 4.1 x 5.3 centimeters in the head region (the right side of the pancreas)."

        pass- "The pancreatic duct (drainage tube) is widened to 5.8 millimeters, which suggests blockage downstream."

- "Bile ducts inside and outside the liver are dilated (swollen), indicating that bile flow is being blocked."

    llm_summary = _call_openai(sanitized_for_model, language)

    if llm_summary:conclusion: Summarize the 1-2 most important findings from the ACTUAL "Conclusion" or "Impression" section in 2-4 clear, simple sentences. Avoid medical jargon. Explain what the findings mean in practical terms.

        summary = {key: (llm_summary.get(key) or "").strip() for key in _JSON_KEYS}CRITICAL for conclusion:

    else:- Rewrite ALL medical terms in plain language

        summary = {key: "" for key in _JSON_KEYS}- Remove garbled phrases like "the patient the" - simplify grammar

- Focus on what matters most to understanding the condition

    # Apply glossary and simplification- Connect findings to likely symptoms or concerns

    def polish(text_block: str) -> str:- Keep sentences short and direct

        text_block = text_block or ""Example STYLE (adapt to actual report): "The scan shows a mass in the head of the pancreas measuring about 4 centimeters. This mass is blocking both the pancreatic duct (which drains digestive enzymes) and the bile ducts (which drain bile from the liver). The blockage is causing bile ducts to swell throughout the liver. These findings suggest a pancreatic tumor that needs urgent medical attention."

        if lay_gloss:

            text_block = lay_gloss.replace_terms(text_block)concern: One clear sentence about next steps appropriate for the ACTUAL findings. Avoid alarming language but be honest.

        sentences = [Example STYLE (adapt to actual report): "These findings should be discussed with your doctor to determine whether physical therapy, medication, or other treatments are appropriate."

            _simplify_sentence(sentence)

            for sentence in _split_sentences(text_block)CRITICAL RULES:

        ]- Extract ALL information from the ACTUAL report provided below - DO NOT use example text

        if not sentences:- Read the "Clinical History" or "Indication" section for the reason - extract the ACTUAL condition/symptoms mentioned

            text_block = _simplify_sentence(text_block)- Read the "Procedure"/"Technique" section for how the scan was done - extract ACTUAL details (MRI vs CT, which body part, Tesla strength, contrast usage, etc.)

            return text_block- Read the "Findings" section for what was discovered - extract ACTUAL anatomical findings

        return " ".join(sentence for sentence in sentences if sentence)- Read the "Conclusion"/"Impression" for the summary - extract ACTUAL diagnostic conclusions

- SIMPLIFY all medical jargon: "hypo-attenuating" → "darker area", "lesion" → "abnormal area or mass", "upstream dilatation" → "swelling upstream"

    reason_text = summary.get("reason") or _infer_reason(sanitized_for_public, sections, metadata, language)- FIX grammatical errors: remove garbled phrases like "the patient the" or "noted mass effect on" - rewrite in clear English

    technique_text = summary.get("technique") or _infer_technique(sanitized_for_public, sections, language)- NO fragments or incomplete sentences - every sentence must be complete and understandable

- KEEP ALL NUMBERS exactly as stated: "5.4 x 5.6 x 6.7 cm" stays "5.4 x 5.6 x 6.7 cm"

    if not summary.get("findings"):- Use medical terms when necessary but ALWAYS explain them in parentheses the same sentence

        findings_items = _extract_key_findings(sections)- Write for an intelligent adult, not a child

    else:- Be empathetic but factual—avoid false reassurance or unnecessary alarm

        findings_items = _split_sentences(summary["findings"])- If language is "{language}", write EVERYTHING in pure {language} with NO English words mixed in.

    if not findings_items:

        findings_items = _extract_key_findings(sections)REMEMBER: The examples above show STYLE and FORMAT only. You MUST extract content from the ACTUAL report text provided below."""



    if not summary.get("conclusion"):

        conclusion_items = _extract_conclusion(sections)    # 1) Try Chat Completions JSON mode when supported.

    else:    chat_model = env_model if _supports_chat_completions(env_model) else chat_fallback

        conclusion_items = _split_sentences(summary["conclusion"])    tried_chat = False

    if not conclusion_items:    if chat_model:

        conclusion_items = _extract_conclusion(sections)        try:

            from openai import APIStatusError  # present in newer sdks; ignore if missing

    concern_text = summary.get("concern") or _infer_concern(sanitized_for_public, language)        except Exception:

            APIStatusError = Exception  # type: ignore

    reason_text = polish(reason_text)

    technique_text = polish(technique_text)        try:

    concern_text = polish(concern_text) if concern_text else ""            tried_chat = True

            resp = client.chat.completions.create(

    findings_html = _render_bullets(findings_items, include_normal=True, language=language)                model=chat_model,

    conclusion_html = _render_bullets(conclusion_items, include_normal=False, language=language)                messages=[

                    {"role":"system","content":instructions},

    comparison_match = re.search(r"(?im)^\s*comparison\s*:\s*(.+)$", sanitized_for_public)                    {"role":"user","content":report_text},

    oral_match = re.search(r"(?im)^\s*oral\s+contrast\s*:\s*(.+)$", sanitized_for_public)                ],

                temperature=float(os.getenv("OPENAI_TEMPERATURE","0.2")),

    words = len(re.findall(r"\w+", sanitized_for_public))                max_tokens=900,

    sentences = len(_split_sentences(sanitized_for_public))                response_format={"type":"json_object"},

    pos_hits = len(re.findall(r'class="ii-pos"', findings_html + conclusion_html))            )

    neg_hits = len(re.findall(r'class="ii-neg"', findings_html + conclusion_html))            data = _extract_json_loose(resp.choices[0].message.content) or {}

            if data:

    patient_bundle = {                out: Dict[str,str] = {}

        "name": metadata.name,                for k in ("reason","technique","findings","conclusion","concern"):

        "age": metadata.age,                    v = data.get(k,"")

        "sex": metadata.sex,                    out[k] = (v if isinstance(v,str) else str(v or "")).strip()

        "hospital": metadata.hospital,                return out

        "date": metadata.date,        except NotFoundError as e:

        "study": metadata.study,            logger.error("Chat model not found: %s", getattr(e, "message", str(e)))

        "history": metadata.history,        except BadRequestError as e:

    }            logger.error("Chat 400 for model=%s: %s", chat_model, getattr(e, "message", str(e)))

        except APIStatusError as e:  # network/http class

    def wrap_text(value: str) -> str:            logger.error("Chat APIStatusError: %s", str(e))

        value = value.strip()        except Exception:

        value = _maybe_translate_sentence(value, language)            logger.exception("OpenAI chat call failed")

        return f'<span class="ii-text" style="color:#ffffff">{value}</span>' if value else ""

    # 2) Fallback to Responses for reasoning models or when chat failed.

    result = {    model = env_model

        "reason": wrap_text(reason_text),    use_temp = not _is_reasoning_model(model)  # temperature often unsupported on reasoning models

        "technique": wrap_text(technique_text),    kwargs = dict(

        "comparison": (comparison_match.group(1).strip() if comparison_match else "None"),        model=model,

        "oral_contrast": (oral_match.group(1).strip() if oral_match else "Not stated"),        instructions=instructions,

        "findings": findings_html,        input=report_text,

        "conclusion": conclusion_html,        max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS","1500")),

        "concern": wrap_text(concern_text) if concern_text else "",    )

        "word_count": words,    if use_temp:

        "sentence_count": sentences,        kwargs["temperature"] = temperature

        "highlights_positive": pos_hits,    if effort in {"low","medium","high","minimal"} and _is_reasoning_model(model):

        "highlights_negative": neg_hits,        kwargs["reasoning"] = {"effort": effort}

        "patient": patient_bundle,

    }    try:

        resp = client.responses.create(**kwargs)

    return result        text = getattr(resp, "output_text", None) or str(resp)

        data = _extract_json_loose(text) or {}

    except BadRequestError as e:

__all__ = ["Glossary", "build_structured"]        msg = getattr(e, "message", str(e))

        logger.error("Responses 400 for model=%s: %s", model, msg)
        # Retry once without temperature if that was the complaint.
        if "Unsupported parameter: 'temperature'" in msg or "temperature" in msg.lower():
            kwargs.pop("temperature", None)
            try:
                resp = client.responses.create(**kwargs)
                text = getattr(resp, "output_text", None) or str(resp)
                data = _extract_json_loose(text) or {}
            except Exception:
                logger.exception("Responses retry without temperature failed")
                data = {}
        else:
            data = {}
    except NotFoundError as e:
        logger.error("Responses model not found: %s", getattr(e, "message", str(e)))
        data = {}
    except Exception:
        logger.exception("OpenAI responses call failed")
        data = {}

    out: Dict[str,str] = {}
    for k in ("reason","technique","findings","conclusion","concern"):
        v = data.get(k,"")
        out[k] = (v if isinstance(v,str) else str(v or "")).strip()
    return out

def _merge_runs(runs: List[Dict[str, str]]) -> Dict[str, str]:
    def norm(x: str) -> str:
        return re.sub(r"\s+"," ", _strip_labels((x or "").strip()).lower())
    out: Dict[str, str] = {}
    for key in ("reason","technique","findings","conclusion","concern"):
        vals = [r.get(key,"") for r in runs if r.get(key)]
        if not vals: out[key] = ""; continue
        counts: Dict[str, Tuple[int,str]] = {}
        for v in vals:
            n = norm(v)
            if n in counts:
                prev_n, prev_v = counts[n]
                counts[n] = (prev_n + 1, prev_v if len(prev_v) >= len(v) else v)
            else:
                counts[n] = (1, v)
        pick = sorted(counts.items(), key=lambda kv: (kv[1][0], len(kv[1][1])), reverse=True)[0][1][1]
        out[key] = pick
    return out

def _clean_kiswahili_text(text: str) -> str:
    """Post-process Kiswahili text to fix common mixed-language issues."""
    if not text:
        return text
    
    # Common English words that slip through → Kiswahili
    replacements = {
        r'\bscan\b': 'uchunguzi',
        r'\bmass\b': 'uvimbe',
        r'\btumor\b': 'uvimbe',
        r'\bnormal\b': 'kawaida',
        r'\babnormal\b': 'si kawaida',
        r'\bbrain\b': 'ubongo',
        r'\bliver\b': 'ini',
        r'\bkidney\b': 'figo',
        r'\bheart\b': 'moyo',
        r'\blungs?\b': 'mapafu',
        r'\bfracture\b': 'mvunjiko',
        r'\bbleed(?:ing)?\b': 'kutokwa na damu',
        r'\bswelling\b': 'uvimbe',
        r'\bpain\b': 'maumivu',
        r'\binflammation\b': 'uvimbe',
        r'\binfection\b': 'maambukizi',
        r'\bct\s+scan\b': 'uchunguzi wa CT',
        r'\bmri\s+scan\b': 'uchunguzi wa MRI',
        r'\bx-ray\b': 'X-ray',
        r'\bultrasound\b': 'uchunguzi wa sauti',
        r'\bfindings?\b': 'matokeo',
        r'\bconclusion\b': 'hitimisho',
        r'\breason\b': 'sababu',
        r'\btechnique\b': 'mbinu',
        r'\bconcern\b': 'wasiwasi',
        r'\bdoctor\b': 'daktari',
        r'\bpatient\b': 'mgonjwa',
        r'\bhospital\b': 'hospitali',
        r'\bthe\b': '',
        r'\band\b': 'na',
        r'\bor\b': 'au',
        r'\bwith\b': 'na',
        r'\bwithout\b': 'bila',
        r'\bin\b': 'ndani ya',
        r'\bon\b': 'juu ya',
        r'\bof\b': 'ya',
        r'\bto\b': 'kwa',
        r'\bfor\b': 'kwa ajili ya',
    }
    
    result = text
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result

def _summarize_with_openai(report_text: str, language: str) -> Dict[str, str] | None:
    if not (os.getenv("INSIDEIMAGING_ALLOW_LLM","0")=="1" and os.getenv("OPENAI_API_KEY")):
        logger.info("[LLM] disabled or missing API key"); return None
    try:
        n = max(1, int(os.getenv("OPENAI_SELF_CONSISTENCY_N","1")))
        effort = (os.getenv("OPENAI_REASONING_EFFORT","") or "").lower()
        base_temp = float(os.getenv("OPENAI_TEMPERATURE","0.2"))
        runs: List[Dict[str,str]] = []
        for i in range(n):
            runs.append(_call_openai_once(report_text, language, min(1.0, base_temp+0.05*i), effort) or {})
        result = (_merge_runs(runs) if len(runs)>1 else runs[0]) or None
        
        # Post-process for Kiswahili to remove English words
        if result and language.lower() in ["kiswahili", "swahili"]:
            for key in ("reason", "technique", "findings", "conclusion", "concern"):
                if key in result:
                    result[key] = _clean_kiswahili_text(result[key])
        
        return result
    except Exception:
        logger.exception("[LLM] summarization failed"); return None

# ---------- extraction ----------
HEAD_WORD = re.compile(r"\b(head|skull|brain)\b", re.I)

def _region_from_text(low: str) -> str | None:
    if any(w in low for w in ["pancreas","pancreatic","liver","hepatic","biliary","gallbladder","kidney","renal","spleen","stomach","bowel","colon"]):
        return "abdomen"
    if any(w in low for w in ["pelvis","uterus","ovary","prostate","bladder","adnexa"]):
        return "pelvis"
    if any(w in low for w in ["chest","thorax","lung","mediastinum","cardiac","heart"]):
        return "chest"
    if any(w in low for w in ["cervical spine","c-spine"]):
        return "cervical spine"
    if any(w in low for w in ["thoracic spine"]):
        return "thoracic spine"
    if any(w in low for w in ["lumbar spine","l-spine","lspine"]):
        return "lumbar spine"
    if ("neck" in low) or ("cervical" in low and "spine" not in low):
        return "neck"
    if HEAD_WORD.search(low) and not re.search(r"\b(head\s+of\s+the\s+pancreas|pancreatic\s+head)\b", low):
        return "head"
    return None

def _extract_technique_details(text: str) -> str:
    low = (text or "").lower()
    modality = "CT" if re.search(r"\bct\b", low) else ("MRI" if "mri" in low else ("Ultrasound" if ("ultrasound" in low or "sonograph" in low) else ("X-ray" if re.search(r"x-?ray|radiograph", low) else None)))
    region = _region_from_text(low)
    planes = [p for p in ["axial","coronal","sagittal"] if p in low]
    has_c = bool(re.search(r"\b(cect|contrast[-\s]?enhanced|with\s+contrast)\b", low))
    has_nc = bool(re.search(r"\b(nect|non[-\s]?contrast|without\s+contrast)\b", low))
    contrast = "with and without contrast" if (has_c and has_nc) else ("with contrast" if has_c else ("without contrast" if has_nc else ""))
    m = re.search(r"from\s+(.+?)\s+to\s+(.+?)[\.;]", text, flags=re.I)
    coverage = f"coverage from {m.group(1).strip()} to {m.group(2).strip()}" if m else ""
    win = "brain window" if "brain window" in low else ""
    parts = []
    if modality: parts.append(f"{'CT scan' if modality=='CT' else modality} of the {region or 'area'}")
    if planes: parts.append(", ".join(planes))
    if contrast: parts.append(contrast)
    if coverage: parts.append(coverage)
    if win: parts.append(win)
    out = ", ".join(parts).strip(", ")
    if out and not out.endswith("."): out += "."
    return out

def _infer_modality_and_region(text: str) -> str:
    low = (text or "").lower()
    modality = "MRI" if "mri" in low else ("CT" if re.search(r"\bct\b", low) else ("Ultrasound" if ("ultrasound" in low or "sonograph" in low) else ("X-ray" if re.search(r"x-?ray|radiograph", low) else None)))
    with_contrast = bool(re.search(r"\b(contrast|cect)\b", low))
    region = _region_from_text(low)
    if not modality: return ""
    if region:
        return f"{'CT scan' if modality=='CT' else modality} of the {region}" + (" with contrast." if modality=='CT' and with_contrast else ".")
    return f"{'CT scan' if modality=='CT' else modality}" + (" with contrast." if modality=='CT' and with_contrast else ".")

def _translate_to_kiswahili(text: str, context: str = "") -> str:
    """Translate simple English fallback text to Kiswahili."""
    translations = {
        "The scan was done to check for a mass.": "Uchunguzi ulifanywa kuangalia uvimbe.",
        "The scan was done to look for a problem in the head.": "Uchunguzi ulifanywa kutafuta tatizo katika kichwa.",
        "The scan was done to look for a problem in the neck.": "Uchunguzi ulifanywa kutafuta tatizo katika shingo.",
        "The scan was done to look for a problem in the abdomen.": "Uchunguzi ulifanywa kutafuta tatizo katika tumbo.",
        "The scan was done to look for a problem in the area.": "Uchunguzi ulifanywa kutafuta tatizo katika eneo.",
        " and swollen lymph nodes.": " na lymph nodes zilizovimba.",
        "The goal was to find a simple cause for the symptoms.": "Lengo lilikuwa kupata sababu rahisi ya dalili.",
    "The scan was ordered to investigate a mass.": "Uchunguzi uliagizwa kuchunguza uvimbe.",
    "The scan was ordered to evaluate the head.": "Uchunguzi uliagizwa kuchunguza kichwa.",
    "The scan was ordered to evaluate the neck.": "Uchunguzi uliagizwa kuchunguza shingo.",
    "The scan was ordered to evaluate the abdomen.": "Uchunguzi uliagizwa kuchunguza tumbo.",
    "The scan was ordered to evaluate the area.": "Uchunguzi uliagizwa kuchunguza eneo hili.",
    "Doctors wanted to understand what is causing the current symptoms.": "Madaktari walitaka kuelewa kinachosababisha dalili za sasa.",
        "Technique not described.": "Mbinu haijaeleweshwa.",
        "Not described.": "Haijaeleweshwa.",
        "No major problems were seen.": "Hakuna matatizo makubwa yaliyoonekana.",
        "Most other areas look normal.": "Maeneo mengine yanaonekana kawaida.",
        "See important findings.": "Tazama matokeo muhimu.",
        "CT scan": "Uchunguzi wa CT",
        "MRI": "Uchunguzi wa MRI",
        "Ultrasound": "Uchunguzi wa sauti",
        "X-ray": "X-ray",
        " of the ": " ya ",
        " with contrast.": " na rangi.",
        " without contrast.": " bila rangi.",
    }
    
    result = text
    for eng, swh in translations.items():
        result = result.replace(eng, swh)
    
    return result

def _infer_reason(text: str, seed: str, language: str = "English") -> str:
    src = (seed or "").strip()
    if not src or src.lower() == "not provided.":
        match = re.search(r"(?im)^\s*(indication|reason|history)\s*:\s*(.+)$", text or "")
        if match:
            src = match.group(2).strip()

    cleaned_seed = _strip_labels(src)
    cleaned_seed = re.sub(r"(?i)\b(history|clinical\s+history)\s*:\s*", "", cleaned_seed).strip()

    if cleaned_seed:
        bullets = _normalize_listish(cleaned_seed)
        sentences: List[str] = []
        if bullets:
            for item in bullets[:2]:
                simple = _simplify(item, None)
                if not simple:
                    continue
                simple = simple.strip()
                if simple and not simple.endswith('.'):
                    simple += '.'
                sentences.append(simple)
        else:
            simple = _simplify(cleaned_seed, None)
            if simple:
                simple = simple.strip()
                if simple and not simple.endswith('.'):
                    simple += '.'
                sentences = _split_sentences(simple) or [simple]
        if sentences:
            reason = " ".join(sentences[:2]).strip()
            if language.lower() in ["kiswahili", "swahili"]:
                reason = _clean_kiswahili_text(reason)
            return reason

    low_all = (text or "").lower() + " " + (src or "").lower()

    region = "head" if any(w in low_all for w in ["head","skull","brain"]) else \
             "neck" if "neck" in low_all else \
             "abdomen" if any(w in low_all for w in ["abdomen","abdominal","belly","pancreas","pancreatic","biliary","liver","hepatic","gallbladder"]) else \
             "area"

    has_mass = bool(re.search(r"\b(mass|lesion|tumou?r|nodule|cyst)\b", low_all))
    has_nodes = bool(re.search(r"\b(adenopathy|lymph\s*node|lymphaden)\b", low_all))

    part1 = "The scan was ordered to investigate a mass." if has_mass else f"The scan was ordered to evaluate the {region}."
    if has_nodes:
        part1 = part1.rstrip('.') + " and swollen lymph nodes."
    part2 = "Doctors wanted to understand what is causing the current symptoms."
    fallback = f"{part1} {part2}".strip()

    if language.lower() in ["kiswahili", "swahili"]:
        fallback = _translate_to_kiswahili(fallback)

    return fallback


# ---------- dedupe and pruning ----------
def _drop_heading_labels_line(s: str) -> str:
    return re.sub(r"(?i)^\s*(findings?|impression|conclusion|summary)\s*:\s*", "", s or "").strip()

def _normalize_sentence(s: str) -> str:
    t = _drop_heading_labels_line(s or "")
    t = re.sub(r"[^a-z0-9\s]", "", t.lower()); t = re.sub(r"\s+"," ",t).strip()
    return t

def _dedupe_sections(findings_text: str, conclusion_text: str) -> Tuple[str, str]:
    f_sents = [_drop_heading_labels_line(x) for x in _split_sentences(findings_text or "")]
    c_sents = [_drop_heading_labels_line(x) for x in _split_sentences(conclusion_text or "")]
    c_norm = {_normalize_sentence(x) for x in c_sents if x}
    f_keep = [s for s in f_sents if _normalize_sentence(s) not in c_norm]
    def uniq(seq: List[str]) -> List[str]:
        seen = set(); out = []
        for s in seq:
            n = _normalize_sentence(s)
            if n and n not in seen: seen.add(n); out.append(s)
        return out
    f_keep = uniq(f_keep); c_keep = uniq(c_sents)
    return (" ".join(f_keep).strip(), " ".join(c_keep).strip())

def _prune_findings_for_public(text: str) -> str:
    kept: List[str] = []
    for sent in _split_sentences(text or ""):
        s = _grammar_cleanup(sent.strip())
        if not s or NOISE_RX.search(s): continue
        low = s.lower()
        has_number = bool(re.search(r"\b\d+(\.\d+)?\s*(mm|cm)\b", low))
        is_key = any(re.search(p, low) for p in [*NEG_PHRASES, r"\bmass\b", r"\bfracture\b", r"\bhernia\b", r"\bherniation\b", r"\bstenosis\b"])
        is_pos_blanket = bool(re.match(r"(?i)^(the\s+rest|other\s+areas)\b", s))
        if re.match(r"(?i)^\s*(impression|conclusion|summary)\s*:", s): continue
        if is_key or has_number or is_pos_blanket: kept.append(s)
    return " ".join(kept[:4])

def _to_colored_bullets_html(raw: str, max_items: int, include_normal: bool, language: str = "English") -> str:
    items: List[str] = []
    sources = _normalize_listish(raw) or _split_sentences(raw or "")
    for s in sources:
        s = _drop_heading_labels_line(s)
        t = _tidy_phrases(_grammar_cleanup(_numbers_simple(_simplify(s, None))))
        t = _dedupe_redundant_noun_phrase(t)
        if not t:
            continue
        # Translate to Kiswahili if needed
        if language.lower() in ["kiswahili", "swahili"]:
            t = _clean_kiswahili_text(t)
        items.append(_highlight_phrasewise(t))
        if len(items) >= max_items - (1 if include_normal else 0):
            break
    if include_normal:
        normal_text = "Most other areas look normal."
        if language.lower() in ["kiswahili", "swahili"]:
            normal_text = "Maeneo mengine yanaonekana kawaida."
        items.append(_highlight_phrasewise(normal_text))
    if not items:
        no_problems_text = "No major problems were seen."
        if language.lower() in ["kiswahili", "swahili"]:
            no_problems_text = "Hakuna matatizo makubwa yaliyoonekana."
        items = [_highlight_phrasewise(no_problems_text)]
    html = "<ul class='ii-list' style='color:#ffffff'>" + "".join(f"<li>{it}</li>" for it in items[:max_items]) + "</ul>"
    return _annotate_terms_outside_tags(html)

# ---------- main API ----------
def build_structured(
    text: str,
    lay_gloss: Glossary | None = None,
    language: str = "English",
    render_style: str = "bullets",
) -> Dict[str, str]:
    try:
        lat_ms = max(0, int(os.getenv("OPENAI_MIN_LATENCY_MS","0")))
        if lat_ms: time.sleep(min(10.0, lat_ms/1000.0))
    except Exception:
        pass

    meta = parse_metadata(text or "")
    cleaned = _preclean_report(text or "")

    hx, cleaned = _extract_history(cleaned)
    secs = sections_from_text(cleaned)

    phi_terms = _collect_phi_terms(meta)
    sanitized_for_model = _redact_phi(cleaned, extra_terms=phi_terms)
    sanitized_for_public = _normalize_phi_placeholders(sanitized_for_model)

    reason_seed = secs.get("reason") or "Not provided."
    if hx: reason_seed = (reason_seed.rstrip(".") + f". History: {hx}.").strip()
    findings_src = _strip_signatures(secs.get("findings") or (cleaned or "Not described."))
    impression_src = _strip_signatures(secs.get("impression") or "")
    findings_src_masked = _normalize_phi_placeholders(_redact_phi(findings_src, extra_terms=phi_terms))
    impression_src_masked = _normalize_phi_placeholders(_redact_phi(impression_src, extra_terms=phi_terms))

    m = re.search(r"(?mi)^\s*comparison\s*:\s*(.+)$", cleaned); comparison = (m.group(1).strip() if m else "")
    m = re.search(r"(?mi)^\s*oral\s+contrast\s*:\s*(.+)$", cleaned); oral_contrast = (m.group(1).strip() if m else "")

    fallback_findings = _simplify(_prune_findings_for_public(findings_src_masked), lay_gloss)
    base_conc = impression_src_masked or ""
    if not base_conc:
        picks: List[str] = []
        search_source = sanitized_for_public or cleaned
        for kw in ["mass","obstruction","compression","dilation","fracture","bleed","appendicitis","adenopathy","necrotic","atrophy","stenosis","herniation"]:
            m2 = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", search_source)
            if m2: picks.append(m2.group(0).strip())
        base_conc = " ".join(dict.fromkeys(picks))
    fallback_conclusion = _simplify(_strip_labels(base_conc) or "See important findings.", lay_gloss)

    concern = ""
    for kw in ["obstruction","compression","invasion","perforation","ischemia"]:
        if re.search(rf"(?i)\b{kw}\b", cleaned):
            concern = f"The findings include {kw}. Discuss next steps with your clinician."
            break
    # no else/fallback here

    # LLM attempt, gated + PHI-redacted
    llm = _summarize_with_openai(sanitized_for_model, language)
    llm_reason = _strip_labels((llm or {}).get("reason","")) if llm else ""
    llm_tech = _strip_labels((llm or {}).get("technique","")) if llm else ""

    raw_findings = (_simplify(_strip_labels((llm or {}).get("findings","")), lay_gloss) if llm else "") or fallback_findings
    raw_conclusion = (_simplify(_strip_labels((llm or {}).get("conclusion","")), lay_gloss) if llm else "") or fallback_conclusion
    raw_findings = _normalize_phi_placeholders(raw_findings)
    raw_conclusion = _normalize_phi_placeholders(raw_conclusion)

    # remove overlap
    raw_findings, raw_conclusion = _dedupe_sections(raw_findings, raw_conclusion)

    concern_txt = (_simplify((llm or {}).get("concern",""), lay_gloss) if llm else "") or concern
    concern_txt = _normalize_phi_placeholders(concern_txt)

    # technique prefer deterministic
    technique_extracted = _extract_technique_details(cleaned) or _infer_modality_and_region(cleaned)
    technique_txt = technique_extracted or _simplify(llm_tech, lay_gloss) or "Technique not described."
    
    # Translate technique fallback to Kiswahili if needed
    if language.lower() in ["kiswahili", "swahili"] and technique_txt == "Technique not described.":
        technique_txt = "Mbinu haijaeleweshwa."
    elif language.lower() in ["kiswahili", "swahili"]:
        technique_txt = _translate_to_kiswahili(technique_txt)

    # reason
    reason_txt = _infer_reason(cleaned, llm_reason or reason_seed, language)
    reason_txt = _normalize_phi_placeholders(reason_txt)
    technique_txt = _normalize_phi_placeholders(technique_txt)

    # render
    findings_html = _to_colored_bullets_html(raw_findings, max_items=4, include_normal=True, language=language)
    conclusion_html = _to_colored_bullets_html(raw_conclusion, max_items=2, include_normal=False, language=language)
    reason_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(reason_txt, lay_gloss)}</span>')
    technique_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(technique_txt, lay_gloss)}</span>')
    concern_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(concern_txt, lay_gloss)}</span>') if concern_txt else ""

    # stats
    words = len(re.findall(r"\w+", cleaned or ""))
    sentences = len(re.findall(r"[.!?]+", cleaned or ""))
    pos_hi = len(re.findall(r'class="ii-pos"', findings_html + conclusion_html))
    neg_hi = len(re.findall(r'class="ii-neg"', findings_html + conclusion_html))

    patient_bundle = {
        "name": meta.get("name", ""),
        "age": meta.get("age", ""),
        "sex": meta.get("sex", ""),
        "hospital": meta.get("hospital", ""),
        "date": meta.get("date", ""),
        "study": meta.get("study", ""),
        "history": hx,
    }

    return {
        "name": patient_bundle.get("name", ""), "age": patient_bundle.get("age", ""), "sex": patient_bundle.get("sex", ""),
        "hospital": patient_bundle.get("hospital", ""), "date": patient_bundle.get("date", ""), "study": patient_bundle.get("study", ""),
        "reason": reason_html.strip(), "technique": technique_html.strip(),
        "comparison": comparison or "None", "oral_contrast": oral_contrast or "Not stated",
        "findings": findings_html.strip(), "conclusion": conclusion_html.strip(), "concern": concern_html.strip(),
        "word_count": words, "sentence_count": sentences, "highlights_positive": pos_hi, "highlights_negative": neg_hi,
        "patient": patient_bundle,
    }

__all__ = ["Glossary", "build_structured"]
