# File Upload Enhancement - Multi-Format Support

## Summary
Expanded file upload capabilities to support multiple file formats beyond PDF, making the medical report translation system accessible to more users.

## Supported File Formats

### Documents
- **PDF** (.pdf) - Uses pdfminer.six for text extraction
- **Word** (.docx) - Uses python-docx library, extracts text from paragraphs and tables
- **Plain Text** (.txt) - Direct UTF-8 decoding

### Images (with OCR via AWS Textract)
- **PNG** (.png)
- **JPEG** (.jpg, .jpeg)
- **HEIF/HEIC** (.heif, .heic) - iOS photo format, converted to JPEG before OCR
- **TIFF** (.tif, .tiff)
- **WebP** (.webp)
- **BMP** (.bmp)

## Technical Implementation

### New Python Functions Added to `app.py`

1. **`_extract_text_from_docx_bytes(data: bytes) -> str`**
   - Extracts text from Word documents
   - Handles both paragraphs and tables
   - Gracefully handles missing python-docx library

2. **`_extract_text_from_heif_bytes(data: bytes) -> str`**
   - Converts HEIF/HEIC (iOS photos) to JPEG
   - Uses pillow-heif for format conversion
   - Leverages existing AWS Textract pipeline for OCR

### Updated Upload Route
The `/upload` route in `app.py` now handles file formats in this order:
1. PDF → PDF extraction
2. HEIF/HEIC → Convert to JPEG → OCR
3. DOCX → Word document extraction
4. Standard images (PNG, JPG, etc.) → OCR
5. Fallback → UTF-8 text decoding

### Dependencies Added
- `python-docx` - Word document parsing
- `pillow-heif` - HEIF/HEIC image conversion

### Frontend Changes
- Updated file input accept attribute in `templates/index.html`
- Added user-friendly format support message
- Accept attribute: `.pdf,.txt,.png,.jpg,.jpeg,.heic,.heif,.docx,.tif,.tiff,.webp,.bmp`

## User Experience Improvements

1. **iOS Compatibility** - Users can now upload photos directly from iPhone/iPad (HEIC format)
2. **Word Document Support** - Medical reports saved as Word documents are now processable
3. **Multiple Image Formats** - Broader compatibility for scanned reports
4. **Clear Format Guidance** - Users see supported formats before uploading
5. **Error Messages** - Specific feedback for HEIF, DOCX, and image extraction failures

## Error Handling

Each format includes specific error messages:
- HEIF/HEIC: "Unable to extract text from the HEIF/HEIC image..."
- DOCX: "Unable to extract text from the Word document..."
- Images: "Unable to extract text from the image (>5MB limit)..."

## Testing Recommendations

1. Test HEIF extraction with actual iOS photos
2. Verify Word document extraction with tables
3. Test 5MB+ images to confirm size limit enforcement
4. Validate text quality from scanned document images
5. Test all formats with actual radiology reports

## Deployment Notes

- Ensure AWS Textract credentials are properly configured
- Install new dependencies: `pip install python-docx pillow-heif`
- Server restart required to load new extraction functions
- Monitor extraction success rates for each format type

## Future Enhancements

Potential additions:
- RTF (Rich Text Format) support
- ODT (OpenDocument) support
- Google Docs integration
- Batch upload capability
- Format conversion UI for unsupported formats
