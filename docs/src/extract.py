"""Functions to extract text from uploaded files.

Supports extraction from PDFs using pdfplumber, images via Tesseract OCR,
and plain text files. Normalizes the extracted text for further parsing
and simplification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
import os

def _clean(s: str) -> str:
    """Clean a raw string by stripping whitespace on each line and collapsing
    multiple blank lines into a single blank line."""
    lines = s.splitlines()
    cleaned_lines = [line.rstrip() for line in lines]
    return "\n".join(cleaned_lines).strip()

def from_pdf(path: Path) -> str:
    """Extract text from a PDF file using pdfplumber.

    Returns the concatenated text of all pages. If pdfplumber is missing,
    raises an ImportError.
    """
    import pdfplumber  # type: ignore
    text_parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return _clean("\n\n".join(text_parts))

def from_image(path: Path) -> str:
    """Extract text from an image file using Tesseract OCR.

    Loads the image, converts to grayscale, enhances contrast and sharpness,
    and then runs OCR. Requires Pillow and pytesseract to be installed.
    If Tesseract isn't installed, raises a RuntimeError with instructions.
    """
    import pytesseract  # type: ignore
    from PIL import Image, ImageOps, ImageFilter  # type: ignore
    # Configure path to tesseract executable if provided via env var
    if os.getenv("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
    img = Image.open(path).convert("L")  # convert to grayscale
    img = ImageOps.autocontrast(img).filter(ImageFilter.SHARPEN)
    # Try OCR with page segmentation mode 6 (single uniform block)
    txt = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
    if len(txt.strip()) < 40:
        # Fallback to automatic page segmentation if text seems too short
        txt = pytesseract.image_to_string(img, lang="eng", config="--psm 3")
    return _clean(txt)

def extract(path: Path) -> Tuple[str, str]:
    """Extract text from a file based on its extension.

    Returns a tuple of the detected file type ('pdf', 'image', 'text', or
    'unknown') and the extracted, cleaned text. Text and unknown types are
    both read as UTF-8; errors are ignored to avoid crashes on binary data.
    """
    ext = path.suffix.lower()
    if ext in {".pdf"}:
        return "pdf", from_pdf(path)
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}:
        return "image", from_image(path)
    if ext in {".txt"}:
        return "text", _clean(path.read_text(encoding="utf-8", errors="ignore"))
    # Default: read file as text if possible
    return "unknown", _clean(path.read_text(encoding="utf-8", errors="ignore"))