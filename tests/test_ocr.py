"""Tests for OCR processing."""

import shutil
from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from glkvm_mcp.ocr import (
    OCRError,
    OCRResult,
    extract_boxes,
    extract_text,
    find_text,
    h264_to_jpeg,
    ocr_screenshot,
    pixel_to_hid,
    process_screenshot,
)

# Skip markers for external dependencies
requires_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
requires_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract not installed"
)


@pytest.fixture
def sample_image_with_text():
    """Create a sample image with readable text."""
    # Create a white image with black text
    img = Image.new("RGB", (400, 100), color="white")
    draw = ImageDraw.Draw(img)
    # Use default font (PIL's built-in)
    draw.text((10, 30), "Hello World Test", fill="black")
    return img


@pytest.fixture
def sample_image_bytes(sample_image_with_text):
    """Get JPEG bytes from sample image."""
    buffer = BytesIO()
    sample_image_with_text.save(buffer, format="JPEG")
    return buffer.getvalue()


class TestOCRResult:
    """Tests for OCRResult class."""

    def test_ocr_result_init(self):
        """OCRResult stores text and boxes."""
        boxes = [{"word": "test", "x": 10, "y": 20}]
        result = OCRResult(text="test text", boxes=boxes)
        assert result.text == "test text"
        assert result.boxes == boxes


class TestH264ToJpeg:
    """Tests for H.264 to JPEG conversion."""

    @requires_ffmpeg
    def test_h264_to_jpeg_invalid_data(self):
        """Invalid H.264 data raises OCRError."""
        with pytest.raises(OCRError) as exc_info:
            h264_to_jpeg(b"not valid h264 data")
        assert "ffmpeg failed" in str(exc_info.value)


class TestExtractText:
    """Tests for text extraction."""

    @requires_tesseract
    def test_extract_text_success(self, sample_image_with_text):
        """extract_text returns extracted string."""
        text = extract_text(sample_image_with_text)
        # Check that some text was extracted (OCR may not be perfect)
        assert isinstance(text, str)

    @requires_tesseract
    def test_extract_text_contains_expected(self, sample_image_with_text):
        """extract_text finds expected words."""
        text = extract_text(sample_image_with_text)
        text_lower = text.lower()
        # At least one of these should be found
        assert "hello" in text_lower or "world" in text_lower or "test" in text_lower

    @requires_tesseract
    def test_extract_text_empty_image(self):
        """extract_text returns empty/whitespace for blank image."""
        blank = Image.new("RGB", (100, 100), color="white")
        text = extract_text(blank)
        assert text.strip() == ""


class TestExtractBoxes:
    """Tests for bounding box extraction."""

    @requires_tesseract
    def test_extract_boxes_success(self, sample_image_with_text):
        """extract_boxes returns list of box dicts."""
        boxes = extract_boxes(sample_image_with_text)
        assert isinstance(boxes, list)

    @requires_tesseract
    def test_extract_boxes_structure(self, sample_image_with_text):
        """Boxes have required fields."""
        boxes = extract_boxes(sample_image_with_text)
        if boxes:  # May be empty if OCR fails
            box = boxes[0]
            assert "word" in box
            assert "x" in box
            assert "y" in box
            assert "width" in box
            assert "height" in box
            assert "confidence" in box

    @requires_tesseract
    def test_extract_boxes_empty_image(self):
        """extract_boxes returns empty list for blank image."""
        blank = Image.new("RGB", (100, 100), color="white")
        boxes = extract_boxes(blank)
        assert boxes == []


class TestFindText:
    """Tests for text finding in boxes."""

    @pytest.fixture
    def sample_boxes(self):
        """Sample OCR boxes for testing."""
        return [
            {"word": "Hello", "x": 10, "y": 20, "width": 50, "height": 20, "confidence": 95},
            {"word": "World", "x": 70, "y": 20, "width": 50, "height": 20, "confidence": 90},
            {"word": "Test", "x": 130, "y": 20, "width": 40, "height": 20, "confidence": 85},
            {"word": "hello", "x": 10, "y": 50, "width": 50, "height": 20, "confidence": 92},
        ]

    def test_find_text_exact_match(self, sample_boxes):
        """find_text finds exact word matches."""
        matches = find_text(sample_boxes, "World")
        assert len(matches) == 1
        assert matches[0]["word"] == "World"

    def test_find_text_case_insensitive(self, sample_boxes):
        """find_text is case-insensitive."""
        matches = find_text(sample_boxes, "hello")
        assert len(matches) == 2  # "Hello" and "hello"

    def test_find_text_partial_match(self, sample_boxes):
        """find_text finds partial matches."""
        matches = find_text(sample_boxes, "ell")
        assert len(matches) == 2  # "Hello" and "hello" contain "ell"

    def test_find_text_no_match(self, sample_boxes):
        """find_text returns empty list for no matches."""
        matches = find_text(sample_boxes, "NotFound")
        assert matches == []

    def test_find_text_adds_center_coordinates(self, sample_boxes):
        """find_text adds center_x and center_y."""
        matches = find_text(sample_boxes, "World")
        assert len(matches) == 1
        match = matches[0]
        assert "center_x" in match
        assert "center_y" in match
        # World: x=70, width=50 -> center_x = 70 + 25 = 95
        # World: y=20, height=20 -> center_y = 20 + 10 = 30
        assert match["center_x"] == 95
        assert match["center_y"] == 30

    def test_find_text_preserves_original_fields(self, sample_boxes):
        """find_text preserves all original box fields."""
        matches = find_text(sample_boxes, "Test")
        assert len(matches) == 1
        match = matches[0]
        assert match["word"] == "Test"
        assert match["x"] == 130
        assert match["confidence"] == 85


class TestPixelToHid:
    """Tests for pixel to HID coordinate conversion."""

    def test_pixel_to_hid_origin(self):
        """(0,0) converts to (0,0)."""
        hid_x, hid_y = pixel_to_hid(0, 0, 1920, 1080)
        assert hid_x == 0
        assert hid_y == 0

    def test_pixel_to_hid_max(self):
        """Max pixel converts to 32767."""
        hid_x, hid_y = pixel_to_hid(1920, 1080, 1920, 1080)
        assert hid_x == 32767
        assert hid_y == 32767

    def test_pixel_to_hid_center(self):
        """Center pixel converts to ~16383."""
        hid_x, hid_y = pixel_to_hid(960, 540, 1920, 1080)
        # 960/1920 * 32767 = 16383.5 -> 16383
        # 540/1080 * 32767 = 16383.5 -> 16383
        assert hid_x == 16383
        assert hid_y == 16383

    def test_pixel_to_hid_various_resolutions(self):
        """Works with different screen sizes."""
        # 4K display
        hid_x, hid_y = pixel_to_hid(1920, 1080, 3840, 2160)
        assert hid_x == 16383  # Half of 3840
        assert hid_y == 16383  # Half of 2160

        # 1080p
        hid_x, hid_y = pixel_to_hid(480, 270, 1920, 1080)
        assert hid_x == 8191  # Quarter
        assert hid_y == 8191  # Quarter

    def test_pixel_to_hid_arbitrary_point(self):
        """Arbitrary coordinates convert correctly."""
        # 100 pixels on 1000 pixel screen = 10% = 3276
        hid_x, hid_y = pixel_to_hid(100, 200, 1000, 1000)
        assert hid_x == int(100 / 1000 * 32767)  # 3276
        assert hid_y == int(200 / 1000 * 32767)  # 6553


class TestProcessScreenshot:
    """Tests for screenshot processing pipeline."""

    @requires_ffmpeg
    def test_process_screenshot_invalid_data(self):
        """Invalid H.264 raises OCRError."""
        with pytest.raises(OCRError):
            process_screenshot(b"invalid h264")


class TestOcrScreenshot:
    """Tests for full OCR pipeline."""

    @requires_ffmpeg
    @requires_tesseract
    def test_ocr_screenshot_invalid_data(self):
        """Invalid H.264 raises OCRError."""
        with pytest.raises(OCRError):
            ocr_screenshot(b"invalid h264")
