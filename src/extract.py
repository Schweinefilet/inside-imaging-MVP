"""Functions to extract text from uploaded files.

Supports extraction from PDFs using pdfplumber, images via Tesseract OCR,
and plain text files. Normalizes the extracted text for further parsing
and simplification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
import os
import boto3, base64


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
    """Extract text from an image file using Amazon Textract DetectDocumentText."""
    import boto3  # local import okay too
    client = boto3.client("textract", region_name=os.getenv("AWS_REGION", "us-east-1"))

    # Read image bytes (DetectDocumentText Bytes supports JPEG/PNG/TIFF)
    with open(path, "rb") as f:
        image_bytes = f.read()

    resp = client.detect_document_text(Document={"Bytes": image_bytes})
    # Textract returns Blocks; pull LINE text in order
    lines = []
    for block in resp.get("Blocks", []):
        if block.get("BlockType") == "LINE" and "Text" in block:
            lines.append(block["Text"])
    return _clean("\n".join(lines))


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
