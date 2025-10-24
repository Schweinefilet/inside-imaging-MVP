"""Utilities for translating radiology reports into patient-friendly language.

The module exposes a small public surface used by :mod:`app`.  It provides a
:class:`Glossary` helper for loading lay-language terminology, wrappers around
:mod:`src.parse` for extracting metadata/sections, and the
:func:`build_structured` entry point that orchestrates report post-processing.

The previous revision of this file became severely corrupted with duplicated
imports and class definitions which made the module impossible to import.  This
rewrite restores a minimal, well-defined API while keeping backward compatible
behaviour for the rest of the application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List
import csv
import json
import logging
import os
import re
import time

logger = logging.getLogger("insideimaging")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

try:  # Prefer the dedicated parsing helpers shipped with the project.
    from .parse import parse_metadata as _parse_metadata, sections_from_text as _sections_from_text
except Exception:  # pragma: no cover - fallback engaged only during packaging errors.
    logger.warning("parse.py unavailable; using simplified metadata parser")

    def _simple_grab(pattern: str, text: str) -> str:
        match = re.search(pattern, text, flags=re.I | re.M)
        return match.group(1).strip() if match else ""

    def parse_metadata(text: str) -> Dict[str, str]:
        blob = text or ""
        return {
            "name": _simple_grab(r"^\s*NAME\s*[:\-]?\s*([^\n]+)", blob),
            "age": _simple_grab(r"^\s*AGE\s*[:\-]?\s*([0-9]{1,3})", blob),
            "sex": _simple_grab(r"^\s*SEX\s*[:\-]?\s*([A-Za-z]+)", blob).upper(),
            "hospital": _simple_grab(r"^[^\n]*HOSPITAL[^\n]*$", blob),
            "date": _simple_grab(r"^\s*DATE\s*[:\-]?\s*([^\n]+)", blob),
            "study": _simple_grab(r"(?m)^(CT|MRI|X[- ]?RAY|ULTRASOUND|USG)[^\n]*$", blob),
        }

    def sections_from_text(text: str) -> Dict[str, str]:
        blob = text or ""
        pattern = re.compile(
            r"(?im)^\s*(clinical\s*history|history|indication|reason|technique|"
            r"procedure(?:\s+and\s+findings)?|findings?|impression|conclusion|summary)\s*[:\-]?\s*"
        )
        matches = [(m.group(1).lower(), m.start(), m.end()) for m in pattern.finditer(blob)]
        if not matches:
            return {
                "reason": "",
                "technique": "",
                "findings": blob.strip(),
                "impression": "",
            }
        matches.append(("__end__", len(blob), len(blob)))
        buckets = {"reason": "", "technique": "", "findings": "", "impression": ""}
        for index in range(len(matches) - 1):
            label, _, start = matches[index]
            next_start = matches[index + 1][1]
            body = blob[start:next_start].strip()
            if not body:
                continue
            if label in ("clinical history", "history", "indication", "reason"):
                buckets["reason"] = (buckets["reason"] + " " + body).strip()
            elif label.startswith("technique"):
                buckets["technique"] = (buckets["technique"] + " " + body).strip()
            elif label.startswith("procedure") or label.startswith("finding"):
                buckets["findings"] = (buckets["findings"] + " " + body).strip()
            elif label in ("impression", "conclusion", "summary"):
                buckets["impression"] = (buckets["impression"] + " " + body).strip()
        return {key: value.strip() for key, value in buckets.items()}

else:
    parse_metadata = _parse_metadata
    sections_from_text = _sections_from_text


@dataclass
class Glossary:
    """Simple case-insensitive glossary for term replacement."""

    mapping: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str) -> "Glossary":
        data: Dict[str, str] = {}
        try:
            with open(path, newline="", encoding="utf-8-sig") as handle:
                for row in csv.reader(handle):
                    if len(row) < 2:
                        continue
                    key = (row[0] or "").strip().lower()
                    value = (row[1] or "").strip()
                    if key:
                        data[key] = value
        except FileNotFoundError:
            logger.warning("glossary file missing: %%s", path)
        except Exception:
            logger.exception("glossary load failed")
        return cls(data)

    def replace_terms(self, text: str) -> str:
        if not text:
            return ""
        result = text
        for key, value in self.mapping.items():
            result = re.sub(rf"\b{re.escape(key)}\b", value, result, flags=re.IGNORECASE)
        return result


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _min_think_seconds() -> float:
    value = os.getenv("OPENAI_THINK_MIN") or os.getenv("OPENAI_THINK_TIME")
    try:
        return float(value) if value else 30.0
    except Exception:
        return 30.0


def _parse_json_loose(blob: str) -> Dict[str, str] | None:
    try:
        return json.loads(blob)
    except Exception:
        match = re.search(r"\{.*\}", blob, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def _responses_api_client():  # pragma: no cover - requires optional dependency
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    timeout = _env_float("OPENAI_TIMEOUT", 60.0)
    try:
        return OpenAI(api_key=api_key, timeout=timeout)
    except TypeError:
        return OpenAI(api_key=api_key)


def _resolve_models() -> tuple[str, str]:
    primary = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    responses = os.getenv("OPENAI_RESPONSES_MODEL", primary)
    chat = os.getenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_CHAT_FALLBACK", primary))
    return responses, chat


def _summarize_with_openai(report_text: str, language: str) -> Dict[str, str] | None:
    responses_model, chat_model = _resolve_models()
    client = _responses_api_client()
    if client is not None:
        try:  # pragma: no cover - network path disabled in CI
            start = time.perf_counter()
            instructions = (
                "You are a medical report summarizer for the public. "
                f"Write all output in {language}. "
                "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern. "
                "Use clear, simple language and short sentences. No treatment advice. "
                "Highlight important phrases by wrapping them in **double asterisks** in findings and conclusion."
            )
            response = client.responses.create(
                model=responses_model,
                instructions=instructions,
                input=[{"role": "user", "content": report_text}],
                reasoning={"effort": "high"},
                max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2048")),
                temperature=0.2,
            )
            elapsed = time.perf_counter() - start
            if elapsed < _min_think_seconds():
                time.sleep(_min_think_seconds() - elapsed)
            text = getattr(response, "output_text", None)
            if not text:
                try:
                    text = response.output[0].content[0].text
                except Exception:
                    text = str(response)
            data = _parse_json_loose(text) or {}
            return {key: data.get(key, "").strip() for key in ("reason", "technique", "findings", "conclusion", "concern")}
        except Exception:
            logger.exception("OpenAI Responses API call failed")

    try:  # pragma: no cover - network path disabled in CI
        from openai import OpenAI  # type: ignore
    except Exception:
        return None

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    try:  # pragma: no cover - network path disabled in CI
        client = OpenAI(api_key=api_key, timeout=_env_float("OPENAI_TIMEOUT", 60.0))
        start = time.perf_counter()
        instructions = (
            "You are a medical report summarizer for the public. "
            f"Write all output in {language}. "
            "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern. "
            "Use clear, simple language and short sentences. No treatment advice. "
            "Highlight important phrases by wrapping them in **double asterisks** in findings and conclusion."
        )
        response = client.chat.completions.create(
            model=chat_model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": report_text},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        elapsed = time.perf_counter() - start
        if elapsed < _min_think_seconds():
            time.sleep(_min_think_seconds() - elapsed)
        content = response.choices[0].message.content
        data = _parse_json_loose(content) or {}
        return {key: data.get(key, "").strip() for key in ("reason", "technique", "findings", "conclusion", "concern")}
    except Exception:
        logger.exception("OpenAI ChatCompletion call failed")
        return None


def simplify_to_layman(text: str, lay_gloss: Glossary | None) -> str:
    glossary = lay_gloss or Glossary()
    if not text.strip():
        return ""
    out = glossary.replace_terms(text)
    out = re.sub(r"\bcm\b", " centimeters", out, flags=re.IGNORECASE)
    out = re.sub(r"\bmm\b", " millimeters", out, flags=re.IGNORECASE)
    out = re.sub(r"\bHU\b", " Hounsfield units", out, flags=re.IGNORECASE)
    return out.strip()


def build_structured(
    text: str,
    lay_gloss: Glossary | None = None,
    language: str = "English",
) -> Dict[str, str]:
    meta = parse_metadata(text)
    sections = sections_from_text(text)

    reason = sections.get("reason") or "Not provided."
    technique = sections.get("technique") or "Not provided."
    findings_source = sections.get("findings") or "Not described."
    impression_source = sections.get("impression")

    if not impression_source:
        picks: List[str] = []
        for keyword in ["mass", "obstruction", "compression", "dilation", "fracture", "bleed", "appendicitis"]:
            match = re.search(rf"(?is)([^.]*\b{keyword}\b[^.]*)\.\s", text + " ")
            if match:
                snippet = match.group(1).strip()
                if snippet and snippet not in picks:
                    picks.append(snippet + ".")
        impression_source = " ".join(picks) or "See important findings."

    llm_out = _summarize_with_openai(text, language)
    if llm_out:
        reason = llm_out.get("reason", reason) or reason
        technique = llm_out.get("technique", technique) or technique
        simplified_findings = llm_out.get("findings", "").strip() or None
        simplified_conclusion = llm_out.get("conclusion", "").strip() or None
        concern = llm_out.get("concern", "") or ""
    else:
        simplified_findings = None
        simplified_conclusion = None
        concern = ""

    if simplified_findings is None:
        simplified_findings = simplify_to_layman(findings_source, lay_gloss)
    if simplified_conclusion is None:
        simplified_conclusion = simplify_to_layman(impression_source, lay_gloss)

    if not concern:
        for keyword in ["obstruction", "compression", "invasion", "perforation", "ischemia"]:
            if re.search(rf"(?i)\b{keyword}\b", text):
                concern = f"The findings include {keyword}. Discuss next steps with your clinician."
                break

    negative_terms = [
        "mass",
        "obstruction",
        "compression",
        "invasion",
        "perforation",
        "ischemia",
        "tumor",
        "cancer",
        "lesion",
        "bleed",
        "rupture",
    ]
    positive_terms = ["normal", "benign", "unremarkable", "no", "none", "stable", "improved"]

    def _classify_highlight(match: re.Match) -> str:
        content = match.group(1)
        lower = content.lower()
        negative_hits = sum(term in lower for term in negative_terms)
        positive_hits = sum(term in lower for term in positive_terms)
        css_class = "positive"
        if negative_hits > positive_hits:
            css_class = "negative"
        return f"<strong class=\"{css_class}\">{content}</strong>"

    simplified_findings = re.sub(r"\*\*(.*?)\*\*", _classify_highlight, simplified_findings)
    simplified_conclusion = re.sub(r"\*\*(.*?)\*\*", _classify_highlight, simplified_conclusion)

    return {
        "name": meta.get("name", ""),
        "age": meta.get("age", ""),
        "sex": meta.get("sex", ""),
        "hospital": meta.get("hospital", ""),
        "date": meta.get("date", ""),
        "study": meta.get("study", ""),
        "reason": reason.strip(),
        "technique": technique.strip(),
        "findings": simplified_findings.strip(),
        "conclusion": simplified_conclusion.strip(),
        "concern": concern.strip(),
    }


__all__ = ["Glossary", "build_structured", "simplify_to_layman", "parse_metadata", "sections_from_text"]
