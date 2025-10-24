from __future__ import annotations

from src.translate import Glossary, build_structured


def _sample_report() -> str:
    return (
        "NAIROBI RADIOLOGY HOSPITAL\n"
        "NAME: Jane Doe\n"
        "AGE: 42\n"
        "SEX: Female\n"
        "DATE: 01/01/2025\n"
        "MRI BRAIN WITH AND WITHOUT CONTRAST\n"
        "\n"
        "CLINICAL HISTORY: Headache and new onset weakness.\n"
        "TECHNIQUE: MRI brain performed without and with contrast.\n"
        "FINDINGS: **Mass** measuring 2.3 cm causes mild compression of the adjacent ventricle.\n"
        "IMPRESSION: Findings concerning for metastatic disease.\n"
    )


def test_build_structured_extracts_sections_and_metadata():
    glossary = Glossary({"mri": "MRI", "mass": "mass"})
    result = build_structured(_sample_report(), glossary)

    assert result["name"] == "Jane Doe"
    assert result["age"] == "42"
    assert result["sex"] == "F"
    assert result["study"].startswith("MRI")
    assert "Headache" in result["reason"]
    assert "MRI" in result["technique"]
    assert "compression" in result["findings"].lower()
    assert result["conclusion"]


def test_build_structured_converts_highlights_to_markup():
    glossary = Glossary()
    result = build_structured(_sample_report(), glossary)

    assert "<strong class=\"negative\">Mass</strong>" in result["findings"]
