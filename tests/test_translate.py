from __future__ import annotations

from src.translate import Glossary, build_structured, simplify_to_layman


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


def test_build_structured_marks_positive_highlights():
    glossary = Glossary()
    report = (
        "NAIROBI RADIOLOGY HOSPITAL\n"
        "NAME: John Doe\n"
        "AGE: 55\n"
        "SEX: Male\n"
        "DATE: 02/02/2025\n"
        "CT CHEST WITH CONTRAST\n"
        "\n"
        "HISTORY: Screening exam.\n"
        "TECHNIQUE: Contrast enhanced CT scan of the chest.\n"
        "FINDINGS: **No mass** or suspicious nodule is seen.\n"
    )

    result = build_structured(report, glossary)

    assert "<strong class=\"positive\">No mass</strong>" in result["findings"]


def test_build_structured_generates_concern_when_keywords_present():
    glossary = Glossary()
    report = (
        "KISUMU IMAGING CENTER\n"
        "NAME: Sam Smith\n"
        "AGE: 33\n"
        "SEX: M\n"
        "DATE: 03/01/2025\n"
        "CT ABDOMEN WITH CONTRAST\n"
        "\n"
        "FINDINGS: There is obstruction of the bowel leading to dilation.\n"
    )

    result = build_structured(report, glossary)

    assert "obstruction" in result["concern"].lower()
    assert result["reason"] == "Not provided."
    assert result["technique"] == "Not provided."
    assert "obstruction" in result["conclusion"].lower()


def test_simplify_to_layman_respects_glossary_and_units():
    glossary = Glossary({"hepatomegaly": "enlarged liver"})
    text = "Hepatomegaly measuring 5 cm with 12 mm lesion."

    simplified = simplify_to_layman(text, glossary)

    assert "enlarged liver" in simplified.lower()
    assert "centimeters" in simplified
    assert "millimeters" in simplified
