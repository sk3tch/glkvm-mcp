"""OCR processing using Tesseract."""

import io
import subprocess

import pytesseract
from PIL import Image


class OCRError(Exception):
    """Error during OCR processing."""

    pass


class OCRResult:
    """Result of OCR processing."""

    def __init__(self, text: str, boxes: list[dict]):
        self.text = text
        self.boxes = boxes  # List of {word, x, y, width, height, confidence}


def h264_to_jpeg(h264_data: bytes) -> bytes:
    """Convert H.264 keyframes to JPEG using ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-f",
                "h264",
                "-i",
                "pipe:0",
                "-vframes",
                "1",
                "-f",
                "image2",
                "-c:v",
                "mjpeg",
                "-q:v",
                "2",
                "pipe:1",
            ],
            input=h264_data,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise OCRError(f"ffmpeg failed: {result.stderr.decode()}")
        return result.stdout
    except FileNotFoundError as e:
        raise OCRError("ffmpeg not found - please install ffmpeg") from e
    except subprocess.TimeoutExpired as e:
        raise OCRError("ffmpeg timed out") from e


def process_screenshot(
    h264_data: bytes,
    max_width: int = 1280,
    max_height: int = 720,
    quality: int = 70,
) -> tuple[bytes, Image.Image, Image.Image]:
    """Convert H.264 to JPEG and return both bytes and PIL Images.

    Args:
        h264_data: Raw H.264 frame data
        max_width: Maximum width for output image (default 1280)
        max_height: Maximum height for output image (default 720)
        quality: JPEG quality 1-100 (default 70)

    Returns:
        Tuple of (compressed jpeg bytes, resized image, original image)
    """
    jpeg_data = h264_to_jpeg(h264_data)
    original_image = Image.open(io.BytesIO(jpeg_data))

    # Calculate resize ratio to fit within max dimensions while maintaining aspect ratio
    width, height = original_image.size
    ratio = min(max_width / width, max_height / height, 1.0)  # Don't upscale

    if ratio < 1.0:
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        resized_image = original_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    else:
        resized_image = original_image

    # Re-encode as JPEG with specified quality
    output = io.BytesIO()
    resized_image.save(output, format="JPEG", quality=quality, optimize=True)
    compressed_jpeg = output.getvalue()

    return compressed_jpeg, resized_image, original_image


def extract_text(image: Image.Image) -> str:
    """Extract text from image using Tesseract."""
    try:
        return pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as e:
        raise OCRError("Tesseract not found - please install tesseract-ocr") from e


def extract_boxes(image: Image.Image) -> list[dict]:
    """Extract text with bounding boxes from image."""
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as e:
        raise OCRError("Tesseract not found - please install tesseract-ocr") from e

    boxes = []
    for i, word in enumerate(data["text"]):
        if word.strip():
            boxes.append(
                {
                    "word": word,
                    "x": data["left"][i],
                    "y": data["top"][i],
                    "width": data["width"][i],
                    "height": data["height"][i],
                    "confidence": data["conf"][i],
                }
            )
    return boxes


def ocr_screenshot(h264_data: bytes) -> tuple[OCRResult, Image.Image]:
    """Process screenshot and extract text with bounding boxes.

    Returns:
        Tuple of (OCRResult, original_image) - OCR is done on original for accuracy
    """
    _, _, original_image = process_screenshot(h264_data)
    text = extract_text(original_image)
    boxes = extract_boxes(original_image)
    return OCRResult(text=text, boxes=boxes), original_image


def find_text(boxes: list[dict], search_text: str) -> list[dict]:
    """Find text in OCR boxes. Returns matching boxes with center coordinates."""
    search_lower = search_text.lower()
    matches = []

    for box in boxes:
        if search_lower in box["word"].lower():
            # Calculate center point
            center_x = box["x"] + box["width"] // 2
            center_y = box["y"] + box["height"] // 2
            matches.append(
                {
                    **box,
                    "center_x": center_x,
                    "center_y": center_y,
                }
            )

    return matches


def pixel_to_hid(
    pixel_x: int, pixel_y: int, screen_width: int, screen_height: int
) -> tuple[int, int]:
    """Convert pixel coordinates to HID coordinates (0-32767)."""
    hid_x = int((pixel_x / screen_width) * 32767)
    hid_y = int((pixel_y / screen_height) * 32767)
    return hid_x, hid_y
