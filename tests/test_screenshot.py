"""Tests for Screenshot class."""

import base64
import tempfile
from pathlib import Path

from glkvm_mcp.sdk.screenshot import Screenshot


class TestScreenshotBasics:
    """Test basic Screenshot functionality."""

    def test_init_with_data(self):
        """Screenshot can be created with raw bytes."""
        data = b"fake png data"
        shot = Screenshot(data)
        assert shot.data == data
        assert shot.format == "png"

    def test_init_with_format(self):
        """Screenshot accepts format parameter."""
        data = b"fake jpeg data"
        shot = Screenshot(data, format="jpeg")
        assert shot.format == "jpeg"

    def test_len_returns_data_size(self):
        """len() returns byte count."""
        data = b"12345"
        shot = Screenshot(data)
        assert len(shot) == 5

    def test_repr(self):
        """repr shows useful info."""
        shot = Screenshot(b"test", format="png")
        assert "4 bytes" in repr(shot)
        assert "png" in repr(shot)


class TestScreenshotSave:
    """Test Screenshot.save() method."""

    def test_save_to_file(self):
        """save() writes data to file."""
        data = b"test image data"
        shot = Screenshot(data)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.png"
            shot.save(path)
            assert path.read_bytes() == data

    def test_save_to_string_path(self):
        """save() accepts string path."""
        data = b"test image data"
        shot = Screenshot(data)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = f"{tmpdir}/test.png"
            shot.save(path)
            assert Path(path).read_bytes() == data


class TestScreenshotBase64:
    """Test Screenshot.to_base64() method."""

    def test_to_base64(self):
        """to_base64() returns correct encoding."""
        data = b"hello world"
        shot = Screenshot(data)
        expected = base64.b64encode(data).decode("ascii")
        assert shot.to_base64() == expected

    def test_to_base64_roundtrip(self):
        """Base64 can be decoded back to original."""
        data = b"\x00\x01\x02\xff\xfe"
        shot = Screenshot(data)
        decoded = base64.b64decode(shot.to_base64())
        assert decoded == data


class TestScreenshotPIL:
    """Test Screenshot PIL integration."""

    def test_to_pil_with_real_image(self):
        """to_pil() works with real PNG data."""
        # Create a minimal valid PNG (1x1 red pixel)
        # PNG signature + IHDR + IDAT + IEND
        png_data = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde"  # 1x1 RGB
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
            b"\x00\x05\xfe\xd4"  # compressed data
            b"\x00\x00\x00\x00IEND\xaeB`\x82"  # IEND
        )
        shot = Screenshot(png_data)
        img = shot.to_pil()
        assert img.width == 1
        assert img.height == 1

    def test_to_pil_caches_result(self):
        """to_pil() caches the PIL image."""
        png_data = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
            b"\x00\x05\xfe\xd4"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        shot = Screenshot(png_data)
        img1 = shot.to_pil()
        img2 = shot.to_pil()
        assert img1 is img2  # Same object

    def test_width_height_size_properties(self):
        """width, height, size properties work."""
        png_data = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
            b"\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
            b"\x00\x05\xfe\xd4"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        shot = Screenshot(png_data)
        assert shot.width == 1
        assert shot.height == 1
        assert shot.size == (1, 1)
