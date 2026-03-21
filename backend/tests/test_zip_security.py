"""Tests for ZIP security (zip slip protection)."""
import pytest
import zipfile
from pathlib import Path
from app.graph.nodes import validate_zip_safety


class TestZipSecurity:
    """Test ZIP file security validation."""

    def test_valid_zip(self, tmp_path):
        """Test validation of safe ZIP file."""
        # Create a safe ZIP file
        zip_path = tmp_path / "safe.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("test.txt", "content")
            zf.writestr("folder/file.txt", "content")

        assert validate_zip_safety(zip_path) is True

    def test_zip_slip_attack(self, tmp_path):
        """Test detection of zip slip attack."""
        # Create malicious ZIP with path traversal
        zip_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Try to write outside current directory
            zf.writestr("../../etc/passwd", "malicious")

        assert validate_zip_safety(zip_path) is False

    def test_absolute_path_attack(self, tmp_path):
        """Test detection of absolute path attack."""
        zip_path = tmp_path / "absolute.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            # Try to write to absolute path
            zf.writestr("/tmp/malicious.txt", "malicious")

        assert validate_zip_safety(zip_path) is False

    def test_mixed_content_safe_zip(self, tmp_path):
        """Test ZIP with nested folders but safe."""
        zip_path = tmp_path / "nested.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("folder/subfolder/file.txt", "content")
            zf.writestr("another.pdf", "content")

        assert validate_zip_safety(zip_path) is True

    def test_empty_zip(self, tmp_path):
        """Test validation of empty ZIP."""
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            pass  # Empty ZIP

        assert validate_zip_safety(zip_path) is True

    def test_zip_with_image_files(self, tmp_path):
        """Test ZIP containing common marksheet file types."""
        zip_path = tmp_path / "images.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("marksheet1.jpg", "fake-image")
            zf.writestr("marksheet2.png", "fake-image")
            zf.writestr("result.pdf", "fake-pdf")

        assert validate_zip_safety(zip_path) is True
