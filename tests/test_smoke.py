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
    assert diagnostics.get("reason") == "ok"
    assert len(diagnostics.get("sections", [])) >= 3
    assert len(diagnostics.get("modalities", [])) >= 1
    assert diagnostics.get("measurement_count", 0) >= 1


def test_triage_rejects_non_medical_document():
    from app import _triage_radiology_report

    syllabus_text = (
        "Course Syllabus for Advanced Creative Writing. "
        "This syllabus outlines the semester schedule, homework circles, and weekly assignments for students. "
        "The professor emphasizes grading policy, Title IX statements, and thoughtful workshop habits for the campus community. "
        "Office hours take place in a quiet studio where the course description is reviewed alongside reading responses. "
        "Students collaborate on narrative exercises, peer feedback journals, and creative prompts unrelated to hospital workflows or technical laboratories. "
        "The canvas site lists course hours, classroom etiquette guidelines, and final exam requirements for the cohort."
    )

    ok, diagnostics = _triage_radiology_report(syllabus_text)
    assert not ok
    assert diagnostics.get("reason") == "non_medical_tokens"
