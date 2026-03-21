"""Tests for schema validation."""
import pytest
from pydantic import ValidationError
from app.models import (
    MarksheetExtract, SubjectExtract, SubjectStatus, ResultStatus,
    MarksheetRecord, SubjectNormalized
)


class TestSubjectExtract:
    """Test SubjectExtract validation."""

    def test_valid_subject(self):
        """Test valid subject data."""
        subject = SubjectExtract(
            subject_name="Physics",
            obtained_marks=85,
            max_marks=100,
            status=SubjectStatus.OK
        )
        assert subject.subject_name == "Physics"
        assert subject.obtained_marks == 85
        assert subject.max_marks == 100
        assert subject.status == SubjectStatus.OK

    def test_subject_with_ab(self):
        """Test subject with AB status."""
        subject = SubjectExtract(
            subject_name="Mathematics",
            obtained_marks=None,
            max_marks=100,
            status=SubjectStatus.AB
        )
        assert subject.obtained_marks is None
        assert subject.status == SubjectStatus.AB


class TestMarksheetExtract:
    """Test MarksheetExtract validation."""

    def test_valid_marksheet(self):
        """Test valid marksheet extraction."""
        data = {
            "student_name": "John Doe",
            "board": "CBSE",
            "exam_session": "March 2024",
            "roll_no": "1234567",
            "dob": "01-01-2006",
            "school": "ABC School",
            "result_status": "PASS",
            "seat_no": "12345",
            "subjects": [
                {
                    "subject_name": "English",
                    "obtained_marks": 85,
                    "max_marks": 100,
                    "status": "OK"
                },
                {
                    "subject_name": "Physics",
                    "obtained_marks": 78,
                    "max_marks": 100,
                    "status": "OK"
                },
                {
                    "subject_name": "Chemistry",
                    "obtained_marks": 82,
                    "max_marks": 100,
                    "status": "OK"
                },
                {
                    "subject_name": "Mathematics",
                    "obtained_marks": 90,
                    "max_marks": 100,
                    "status": "OK"
                },
                {
                    "subject_name": "Computer Science",
                    "obtained_marks": 88,
                    "max_marks": 100,
                    "status": "OK"
                }
            ]
        }

        marksheet = MarksheetExtract(**data)
        assert marksheet.student_name == "John Doe"
        assert marksheet.board == "CBSE"
        assert len(marksheet.subjects) == 5

    def test_marksheet_limits_subjects_to_five(self):
        """Test that only 5 subjects are kept."""
        data = {
            "student_name": "Test",
            "board": "CBSE",
            "subjects": [
                {"subject_name": f"Subject {i}", "obtained_marks": 80, "max_marks": 100, "status": "OK"}
                for i in range(7)  # 7 subjects
            ]
        }

        marksheet = MarksheetExtract(**data)
        assert len(marksheet.subjects) == 5  # Should limit to 5


class TestSubjectNormalized:
    """Test SubjectNormalized validation."""

    def test_valid_normalized_subject(self):
        """Test valid normalized subject."""
        subject = SubjectNormalized(
            raw_name="PHYSICS (042)",
            normalized_name="PHYSICS",
            category="SCIENCE",
            obtained_marks=85,
            max_marks=100,
            status=SubjectStatus.OK
        )
        assert subject.normalized_name == "PHYSICS"
        assert subject.category == "SCIENCE"

    def test_needs_review_flag(self):
        """Test needs review flag is set correctly."""
        subject = SubjectNormalized(
            raw_name="English",
            normalized_name="ENGLISH",
            category="ENGLISH",
            obtained_marks=None,  # Missing marks
            max_marks=100,
            status=SubjectStatus.AB,
            needs_review=True
        )
        assert subject.needs_review is True


class TestMarksheetRecord:
    """Test MarksheetRecord validation."""

    def test_valid_record(self):
        """Test valid marksheet record."""
        subjects = [
            SubjectNormalized(
                raw_name="English",
                normalized_name="ENGLISH",
                category="ENGLISH",
                obtained_marks=85,
                max_marks=100,
                status=SubjectStatus.OK
            )
        ]

        record = MarksheetRecord(
            id="test-id",
            filename="test.pdf",
            status="completed",
            student_name="Test Student",
            subjects=subjects
        )
        assert record.id == "test-id"
        assert record.filename == "test.pdf"
        assert record.status == "completed"

    def test_record_status_enum(self):
        """Test record status values."""
        valid_statuses = ["pending", "processing", "completed", "error", "needs_review"]
        for status in valid_statuses:
            record = MarksheetRecord(
                id="test-id",
                filename="test.pdf",
                status=status
            )
            assert record.status == status

    def test_record_default_values(self):
        """Test record default field values."""
        record = MarksheetRecord(
            id="test-id",
            filename="test.pdf"
        )
        assert record.status == "pending"
        assert record.board == "CBSE"
        assert record.needs_review is False
        assert record.subjects == []
        assert record.review_reasons == []
        assert record.overall_percent is None
        assert record.pcm_percent is None
