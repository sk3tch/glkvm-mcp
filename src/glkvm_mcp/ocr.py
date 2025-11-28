"""OCR processing using Tesseract."""

import io
import subprocess
from typing import Optional

from PIL import Image
import pytesseract


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
                "-f", "h264",
                "-i", "pipe:0",
                "-vframes", "1",
                "-f", "image2",
                "-c:v", "mjpeg",
                "-q:v", "2",
                "pipe:1",
            ],
            input=h264_data,
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise OCRError(f"ffmpeg failed: {result.stderr.decode()}")
        return result.stdout
    except FileNotFoundError:
        raise OCRError("ffmpeg not found - please install ffmpeg")
    except subprocess.TimeoutExpired:
        raise OCRError("ffmpeg timed out")


def process_screenshot(h264_data: bytes) -> tuple[bytes, Image.Image]:
    """Convert H.264 to JPEG and return both bytes and PIL Image."""
    jpeg_data = h264_to_jpeg(h264_data)
    image = Image.open(io.BytesIO(jpeg_data))
    return jpeg_data, image


def extract_text(image: Image.Image) -> str:
    """Extract text from image using Tesseract."""
    try:
        return pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError:
        raise OCRError("Tesseract not found - please install tesseract-ocr")


def extract_boxes(image: Image.Image) -> list[dict]:
    """Extract text with bounding boxes from image."""
    try:
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError:
        raise OCRError("Tesseract not found - please install tesseract-ocr")

    boxes = []
    for i, word in enumerate(data["text"]):
        if word.strip():
            boxes.append({
                "word": word,
                "x": data["left"][i],
                "y": data["top"][i],
                "width": data["width"][i],
                "height": data["height"][i],
                "confidence": data["conf"][i],
            })
    return boxes


def ocr_screenshot(h264_data: bytes) -> OCRResult:
    """Process screenshot and extract text with bounding boxes."""
    _, image = process_screenshot(h264_data)
    text = extract_text(image)
    boxes = extract_boxes(image)
    return OCRResult(text=text, boxes=boxes)


def find_text(boxes: list[dict], search_text: str) -> list[dict]:
    """Find text in OCR boxes. Returns matching boxes with center coordinates."""
    search_lower = search_text.lower()
    matches = []

    for box in boxes:
        if search_lower in box["word"].lower():
            # Calculate center point
            center_x = box["x"] + box["width"] // 2
            center_y = box["y"] + box["height"] // 2
            matches.append({
                **box,
                "center_x": center_x,
                "center_y": center_y,
            })

    return matches


def pixel_to_hid(pixel_x: int, pixel_y: int, screen_width: int, screen_height: int) -> tuple[int, int]:
    """Convert pixel coordinates to HID coordinates (0-32767)."""
    hid_x = int((pixel_x / screen_width) * 32767)
    hid_y = int((pixel_y / screen_height) * 32767)
    return hid_x, hid_y
