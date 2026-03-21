"""Pytest configuration and fixtures."""
import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file with given name and content."""
    def _make_file(name: str, content: str = "test content"):
        file_path = tmp_path / name
        file_path.write_text(content)
        return file_path
    return _make_file


@pytest.fixture
def temp_image(tmp_path):
    """Create a temporary test image with given name and size."""
    def _make_image(name: str, size: tuple = (100, 100)):
        from PIL import Image
        img = Image.new('RGB', size, color='white')
        file_path = tmp_path / name
        img.save(file_path, 'PNG')
        return file_path
    return _make_image


@pytest.fixture
def sample_subjects():
    """Create a standard set of 5 valid subjects for testing."""
    from app.models import SubjectNormalized, SubjectStatus
    return [
        SubjectNormalized(
            raw_name="English Core", normalized_name="ENGLISH",
            category="ENGLISH", obtained_marks=85, max_marks=100,
            status=SubjectStatus.OK
        ),
        SubjectNormalized(
            raw_name="Mathematics", normalized_name="MATHEMATICS",
            category="MATH", obtained_marks=90, max_marks=100,
            status=SubjectStatus.OK
        ),
        SubjectNormalized(
            raw_name="Science", normalized_name="SCIENCE",
            category="SCIENCE", obtained_marks=82, max_marks=100,
            status=SubjectStatus.OK
        ),
        SubjectNormalized(
            raw_name="Social Science", normalized_name="SOCIAL SCIENCE",
            category="SOCIAL_SCIENCE", obtained_marks=78, max_marks=100,
            status=SubjectStatus.OK
        ),
        SubjectNormalized(
            raw_name="Hindi", normalized_name="HINDI",
            category="SECOND_LANGUAGE", obtained_marks=88, max_marks=100,
            status=SubjectStatus.OK
        ),
    ]
