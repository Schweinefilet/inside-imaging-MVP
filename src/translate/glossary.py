"""Optional lay-language glossary loaded from a CSV at startup."""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from typing import Dict

logger = logging.getLogger("insideimaging.translate.glossary")


@dataclass
class Glossary:
    terms: Dict[str, str]

    @classmethod
    def load(cls, path: str) -> "Glossary":
        terms: Dict[str, str] = {}
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    term = (row.get("term") or row.get("Term") or "").strip()
                    definition = (row.get("definition") or row.get("Definition") or "").strip()
                    if term:
                        terms[term.lower()] = definition
        except Exception:
            logger.exception("Failed to load glossary from %s", path)
        return cls(terms)
