"""Tests for subject normalization."""
import pytest
from app.services.normalize import (
    normalize_subject_name,
    normalize_subjects,
    compute_best_five_percent,
    compute_core_percent,
    get_core_subjects,
    compute_review_reasons
)
from app.models import SubjectNormalized, SubjectStatus


class TestSubjectNormalization:
    """Test subject name normalization."""

    def test_normalize_english_variants(self):
        """Test various English subject name variants."""
        test_cases = [
            ("ENGLISH CORE", "ENGLISH"),
            ("English Language", "ENGLISH"),
            ("eng", "ENGLISH"),
            ("English Communicative", "ENGLISH"),
        ]

        for raw, expected in test_cases:
            normalized, category = normalize_subject_name(raw)
            assert normalized == expected, f"Failed for {raw}: got {normalized}"
            assert category == "ENGLISH"

    def test_normalize_math_variants(self):
        """Test various Math subject name variants."""
        test_cases = [
            ("MATHEMATICS", "MATHEMATICS"),
            ("MATHS", "MATHEMATICS"),
            ("MATHEMATICS BASIC", "MATHEMATICS"),
        ]

        for raw, expected in test_cases:
            normalized, category = normalize_subject_name(raw)
            assert normalized == expected, f"Failed for {raw}: got {normalized}"
            assert category == "MATH"

    def test_normalize_unknown_subject(self):
        """Test unknown subject returns original name."""
        normalized, category = normalize_subject_name("Unknown Subject XYZ")
        assert normalized == "Unknown Subject XYZ"
        assert category == "OTHER"

    def test_normalize_empty_subject(self):
        """Test empty subject handling."""
        normalized, category = normalize_subject_name(None)
        assert normalized == "UNKNOWN"
        assert category == "OTHER"

    def test_normalize_subjects_list(self):
        """Test normalizing a list of subjects."""
        raw_subjects = [
            {"subject_name": "ENGLISH CORE", "obtained_marks": 85, "max_marks": 100, "status": "OK"},
            {"subject_name": "MATHEMATICS", "obtained_marks": 90, "max_marks": 100, "status": "OK"},
            {"subject_name": "SCIENCE", "obtained_marks": 82, "max_marks": 100, "status": "OK"},
            {"subject_name": "SOCIAL SCIENCE", "obtained_marks": 78, "max_marks": 100, "status": "OK"},
            {"subject_name": "HINDI", "obtained_marks": 88, "max_marks": 100, "status": "OK"},
        ]

        normalized = normalize_subjects(raw_subjects)

        # Should pad to 6 subjects (5 main + 1 placeholder)
        assert len(normalized) == 6
        assert normalized[0].normalized_name == "ENGLISH"
        assert normalized[1].normalized_name == "MATHEMATICS"
        assert normalized[2].normalized_name == "SCIENCE"
        assert normalized[3].normalized_name == "SOCIAL SCIENCE"
        assert normalized[5].normalized_name == "EXTRA"  # placeholder

    def test_normalize_subjects_ab_status(self):
        """Test that AB status sets obtained_marks to None."""
        raw_subjects = [
            {"subject_name": "ENGLISH", "obtained_marks": 0, "max_marks": 100, "status": "AB"},
        ]

        normalized = normalize_subjects(raw_subjects)
        assert normalized[0].obtained_marks is None
        assert normalized[0].status == SubjectStatus.AB

    def test_normalize_science_variants(self):
        """Test various Science subject name variants."""
        test_cases = [
            ("SCIENCE", "SCIENCE"),
            ("PHYSICS", "PHYSICS"),
            ("CHEMISTRY", "CHEMISTRY"),
            ("BIOLOGY", "BIOLOGY"),
        ]

        for raw, expected in test_cases:
            normalized, category = normalize_subject_name(raw)
            assert normalized == expected, f"Failed for {raw}: got {normalized}"
            assert category == "SCIENCE"


class TestComputations:
    """Test percentage computations."""

    def _make_subject(self, name, category, obtained, max_marks=100, status=SubjectStatus.OK):
        return SubjectNormalized(
            raw_name=name, normalized_name=name, category=category,
            obtained_marks=obtained, max_marks=max_marks, status=status
        )

    def test_best_five_percent(self):
        """Test Best of 5 percentage calculation."""
        subjects = [
            self._make_subject("ENGLISH", "ENGLISH", 85),
            self._make_subject("MATHEMATICS", "MATH", 90),
            self._make_subject("SCIENCE", "SCIENCE", 82),
            self._make_subject("SOCIAL SCIENCE", "SOCIAL_SCIENCE", 78),
            self._make_subject("HINDI", "SECOND_LANGUAGE", 88),
        ]

        percent = compute_best_five_percent(subjects)
        # English(85) + Math(90) + Science(82) are mandatory, then best 2 of remaining: Hindi(88) + SS(78)
        expected = (85 + 90 + 82 + 88 + 78) / 500 * 100
        assert percent == round(expected, 2)

    def test_best_five_percent_insufficient_subjects(self):
        """Test Best of 5 with fewer than 5 valid subjects."""
        subjects = [
            self._make_subject("ENGLISH", "ENGLISH", 85),
            self._make_subject("MATHEMATICS", "MATH", 90),
        ]

        percent = compute_best_five_percent(subjects)
        assert percent is None

    def test_core_percent(self):
        """Test core percentage (Eng, Math, Sci, SS)."""
        subjects = [
            self._make_subject("ENGLISH", "ENGLISH", 85),
            self._make_subject("MATHEMATICS", "MATH", 90),
            self._make_subject("SCIENCE", "SCIENCE", 80),
            self._make_subject("SOCIAL SCIENCE", "SOCIAL_SCIENCE", 70),
            self._make_subject("HINDI", "SECOND_LANGUAGE", 88),
        ]

        percent = compute_core_percent(subjects)
        expected = (85 + 90 + 80 + 70) / 4
        assert percent == round(expected, 2)

    def test_core_percent_missing_subject(self):
        """Test core percent when a core subject is missing."""
        subjects = [
            self._make_subject("ENGLISH", "ENGLISH", 85),
            self._make_subject("MATHEMATICS", "MATH", 90),
            self._make_subject("HINDI", "SECOND_LANGUAGE", 88),
        ]

        percent = compute_core_percent(subjects)
        assert percent is None

    def test_get_core_subjects(self):
        """Test extracting core subjects."""
        subjects = [
            self._make_subject("ENGLISH", "ENGLISH", 85),
            self._make_subject("MATHEMATICS", "MATH", 90),
            self._make_subject("SCIENCE", "SCIENCE", 80),
            self._make_subject("SOCIAL SCIENCE", "SOCIAL_SCIENCE", 70),
            self._make_subject("HINDI", "SECOND_LANGUAGE", 88),
        ]

        core = get_core_subjects(subjects)

        assert core["english"] is not None
        assert core["math"] is not None
        assert core["science"] is not None
        assert core["social_science"] is not None
        assert core["second_language"] is not None
        assert core["english"].obtained_marks == 85
        assert core["math"].obtained_marks == 90


class TestReviewReasons:
    """Test review reason generation."""

    def test_review_reasons_for_ab_subject(self):
        """Test review reasons for absent subject."""
        subjects = [
            SubjectNormalized(
                raw_name="English", normalized_name="ENGLISH", category="ENGLISH",
                obtained_marks=None, max_marks=100, status=SubjectStatus.AB
            ),
        ]

        reasons = compute_review_reasons(subjects)
        assert len(reasons) > 0
        assert any("AB" in r for r in reasons)

    def test_review_reasons_for_missing_marks(self):
        """Test review reasons for missing marks."""
        subjects = [
            SubjectNormalized(
                raw_name="English", normalized_name="ENGLISH", category="ENGLISH",
                obtained_marks=None, max_marks=None, status=SubjectStatus.UNKNOWN
            ),
        ]

        reasons = compute_review_reasons(subjects)
        assert len(reasons) > 0
        assert any("Missing" in r for r in reasons)

    def test_review_reasons_clean_record(self):
        """Test review reasons for clean record."""
        subjects = [
            SubjectNormalized(
                raw_name="English", normalized_name="ENGLISH", category="ENGLISH",
                obtained_marks=85, max_marks=100, status=SubjectStatus.OK
            ),
        ]

        reasons = compute_review_reasons(subjects)
        assert len(reasons) == 0

    def test_review_reasons_compartment_status(self):
        """Test review reasons for compartment subject."""
        subjects = [
            SubjectNormalized(
                raw_name="Mathematics", normalized_name="MATHEMATICS", category="MATH",
                obtained_marks=None, max_marks=100, status=SubjectStatus.COMPARTMENT
            ),
        ]

        reasons = compute_review_reasons(subjects)
        assert len(reasons) > 0
        assert any("COMPARTMENT" in r for r in reasons)
