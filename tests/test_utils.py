"""Tests for pure utility functions — no database or HTTP required."""

import pytest
from src.db.patients import (
    _format_tags_display,
    _parse_age,
    detect_disease_tags,
    truncate_name,
    normalize_study_name,
)
from src.db.stats import _age_bucket, _gender_bucket


# --- truncate_name ---

def test_truncate_name_basic():
    assert truncate_name("John Doe") == "J*** D***"

def test_truncate_name_single_word():
    assert truncate_name("Madonna") == "M***"

def test_truncate_name_empty():
    assert truncate_name("") == ""

def test_truncate_name_none_equivalent():
    assert truncate_name(None) == ""  # type: ignore[arg-type]


# --- _parse_age ---

def test_parse_age_plain_number():
    assert _parse_age("45") == 45

def test_parse_age_with_unit():
    assert _parse_age("45Y") == 45
    assert _parse_age("45 years") == 45

def test_parse_age_none():
    assert _parse_age(None) is None

def test_parse_age_non_numeric():
    assert _parse_age("unknown") is None


# --- _age_bucket ---

def test_age_bucket_boundaries():
    assert _age_bucket(0) == "0-17"
    assert _age_bucket(17) == "0-17"
    assert _age_bucket(18) == "18-30"
    assert _age_bucket(30) == "18-30"
    assert _age_bucket(31) == "31-50"
    assert _age_bucket(65) == "51-65"
    assert _age_bucket(66) == "66+"
    assert _age_bucket(100) == "66+"


# --- _gender_bucket ---

def test_gender_bucket():
    assert _gender_bucket("Male") == "male"
    assert _gender_bucket("M") == "male"
    assert _gender_bucket("female") == "female"
    assert _gender_bucket("F") == "female"
    assert _gender_bucket("Other") == "other"
    assert _gender_bucket("") == "other"
    assert _gender_bucket(None) == "other"  # type: ignore[arg-type]


# --- _format_tags_display ---

def test_format_tags_underscore_replaced():
    result = _format_tags_display(["lung_disease"])
    assert result == ["Lung Disease"]

def test_format_tags_title_case():
    result = _format_tags_display(["oncology", "fracture"])
    assert result == ["Oncology", "Fracture"]

def test_format_tags_empty_filtered():
    result = _format_tags_display(["oncology", "", "fracture"])
    assert "" not in result
    assert len(result) == 2


# --- detect_disease_tags ---

def test_detect_disease_tags_oncology():
    tags = detect_disease_tags("There is a 2cm tumor in the right lobe.")
    assert "oncology" in tags

def test_detect_disease_tags_normal():
    tags = detect_disease_tags("Findings are normal. No acute abnormality.")
    assert "normal" in tags

def test_detect_disease_tags_normal_excluded_when_others_present():
    tags = detect_disease_tags("Normal background with a suspicious mass.")
    assert "normal" not in tags
    assert "oncology" in tags

def test_detect_disease_tags_empty_returns_general():
    tags = detect_disease_tags("")
    assert tags == ["general"]


# --- normalize_study_name ---

def test_normalize_study_name_ct_chest():
    assert normalize_study_name("CT Chest") == "CT Chest"

def test_normalize_study_name_mri_brain():
    assert normalize_study_name("MRI Brain") == "MRI Head"

def test_normalize_study_name_unknown():
    assert normalize_study_name("unknown") == "Unknown"
    assert normalize_study_name("") == "Unknown"

def test_normalize_study_name_with_contrast():
    result = normalize_study_name("CT Abdomen with contrast")
    assert "CT" in result
    assert "contrast" in result.lower()
