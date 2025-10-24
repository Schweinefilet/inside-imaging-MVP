import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_ci_runs():
    assert True


def test_triage_accepts_radiology_report():
    from app import _triage_radiology_report

    radiology_text = (
        "TECHNIQUE: MRI brain performed without and with intravenous contrast.\n"
        "FINDINGS: There is a 2.3 cm enhancing mass in the right frontal lobe with surrounding edema.\n"
        "IMPRESSION: Findings are suspicious for metastatic disease."
    )

    ok, diagnostics = _triage_radiology_report(radiology_text)
    assert ok, diagnostics


def test_triage_rejects_non_medical_document():
    from app import _triage_radiology_report

    syllabus_text = (
        "Course Syllabus for Advanced Creative Writing\n"
        "Course Description: This semester we explore narrative forms and workshop peer drafts.\n"
        "Title IX statements, grading policy, office hours, and assignment schedule are included."
    )

    ok, diagnostics = _triage_radiology_report(syllabus_text)
    assert not ok
    assert diagnostics.get("reason") in {
        "non_medical_tokens",
        "insufficient_radiology_markers",
        "low_confidence",
        "too_short",
    }
