"""Screenshot class with lazy PIL loading."""

import base64
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


class Screenshot:
    """A screenshot captured from a KVM device.

    Provides multiple ways to access the image data:
    - .data: Raw bytes (PNG format)
    - .save(): Save to file
    - .to_base64(): Get base64 encoded string
    - .to_pil(): Convert to PIL Image (requires pillow)
    """

    def __init__(self, data: bytes, format: str = "png"):
        """Initialize with raw image data.

        Args:
            data: Raw image bytes (PNG or JPEG)
            format: Image format ("png" or "jpeg")
        """
        self._data = data
        self._format = format
        self._pil_image: Image.Image | None = None

    @property
    def data(self) -> bytes:
        """Get raw image bytes."""
        return self._data

    @property
    def format(self) -> str:
        """Get image format (png or jpeg)."""
        return self._format

    def __len__(self) -> int:
        """Return the size of the image data in bytes."""
        return len(self._data)

    def __repr__(self) -> str:
        return f"Screenshot({len(self._data)} bytes, format={self._format})"

    def save(self, path: str | Path) -> None:
        """Save screenshot to file.

        Args:
            path: File path to save to. Extension determines format if different
                  from original.
        """
        path = Path(path)
        path.write_bytes(self._data)

    def to_base64(self) -> str:
        """Get base64 encoded string of image data."""
        return base64.b64encode(self._data).decode("ascii")

    def to_pil(self) -> "Image.Image":
        """Convert to PIL Image.

        Requires pillow to be installed.

        Returns:
            PIL Image object

        Raises:
            ImportError: If pillow is not installed
        """
        if self._pil_image is not None:
            return self._pil_image

        try:
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                "pillow is required for PIL conversion. Install it with: pip install pillow"
            ) from e

        self._pil_image = Image.open(BytesIO(self._data))
        return self._pil_image

    @property
    def width(self) -> int:
        """Get image width in pixels. Requires pillow."""
        return self.to_pil().width

    @property
    def height(self) -> int:
        """Get image height in pixels. Requires pillow."""
        return self.to_pil().height

    @property
    def size(self) -> tuple[int, int]:
        """Get image size as (width, height). Requires pillow."""
        img = self.to_pil()
        return (img.width, img.height)
