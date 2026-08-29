"""Tests for src.parse.parse_metadata study-name extraction.

Consolidated from throwaway root-level scripts (debug_parse.py, test_parse.py,
test_procedure.py, test_simplified.py) into real regression tests.
"""

import pytest

from src.parse import parse_metadata


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "PROCEDURE DETAILS\n"
            "CT (special x-ray) of your tummy and pelvis with contrast. "
            "Thin slices were taken and shown in different views.",
            "CT of abdomen and pelvis (with contrast)",
        ),
        (
            "PROCEDURE DETAILS\nMRI scan of your brain.",
            "MRI of brain",
        ),
        (
            "PROCEDURE DETAILS\n"
            "X-ray (plain film) of your foot with thin views to see the "
            "bones and joints clearly.",
            "X-ray of foot",
        ),
        (
            "EXAMINATION: CT Chest with contrast",
            "CT of chest (with contrast)",
        ),
        (
            "CT scan (special x-ray) of your chest was done with thin slices.",
            "CT of chest",
        ),
        (
            "PROCEDURE DETAILS\nCT Chest with contrast",
            "CT of chest (with contrast)",
        ),
    ],
)
def test_study_name_extraction(text, expected):
    assert parse_metadata(text)["study"] == expected


def test_verbose_mri_is_simplified():
    """Verbose 'Multiplanar multisequential MRI scans of the lumbar spine
    were obtained' collapses to a concise MRI study name."""
    result = parse_metadata(
        "PROCEDURE DETAILS\n"
        "Multiplanar multisequential MRI scans of the lumbar spine were obtained."
    )["study"]
    assert result.startswith("MRI of lumbar spine")


def test_parse_metadata_returns_expected_keys():
    result = parse_metadata("PROCEDURE DETAILS\nMRI scan of your brain.")
    assert {"study"}.issubset(result)
