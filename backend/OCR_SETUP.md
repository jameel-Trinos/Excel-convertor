# OCR Setup Guide

This guide explains how to set up and configure OCR support for the PDF to Excel conversion system.

## System Requirements

### macOS
```bash
# Install Tesseract OCR
brew install tesseract

# Install Poppler (required for pdf2image)
brew install poppler

# Optional: Install additional language packs
brew install tesseract-lang
```

### Ubuntu/Debian
```bash
# Install Tesseract OCR
sudo apt-get update
sudo apt-get install tesseract-ocr

# Install Poppler
sudo apt-get install poppler-utils

# Optional: Install additional language packs
sudo apt-get install tesseract-ocr-eng tesseract-ocr-hin
```

### Windows
1. Download Tesseract installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location (usually `C:\Program Files\Tesseract-OCR`)
3. Add to PATH or set `TESSDATA_PREFIX` environment variable
4. Download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases
5. Extract and add `bin` folder to PATH

## Python Dependencies

All required packages are already in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key OCR packages:
- `pytesseract>=0.3.10` - Python wrapper for Tesseract OCR
- `pdf2image>=1.16.3` - Convert PDF pages to images
- `easyocr>=1.7.0` - Fallback OCR engine
- `opencv-python-headless>=4.8.0` - Image preprocessing

## Configuration

### OCR Configuration Options

The `OCRConfig` class in `ocr_processor.py` provides these options:

```python
from app.ocr_processor import OCRConfig

config = OCRConfig(
    # Image preprocessing
    dpi=300,                    # Resolution (200-400 recommended)
    denoise=True,               # Remove noise from scanned images
    deskew=True,                # Correct skewed/scanned text
    contrast_enhance=True,      # Improve contrast
    binarize=False,             # Convert to black/white (use for very clean scans)
    
    # OCR engine settings
    language="eng",             # Language code (eng, hin, etc.)
    psm=6,                      # Page segmentation mode (6 = uniform block)
    oem=3,                      # OCR Engine mode (3 = default)
    
    # Quality thresholds
    min_confidence=60.0,        # Minimum confidence (0-100)
    
    # Fallback
    use_easyocr_fallback=True   # Use EasyOCR if Tesseract fails
)
```

### Page Segmentation Modes (PSM)

- `0` - Orientation and script detection (OSD) only
- `1` - Automatic page segmentation with OSD
- `3` - Fully automatic page segmentation (default)
- `4` - Assume single column of text
- `5` - Assume single uniform block of text
- `6` - Assume single uniform block of text (recommended for tables)
- `7` - Treat image as single text line
- `8` - Treat image as single word
- `9` - Treat image as single word in a circle
- `10` - Treat image as single character

**For election Form 20 tables, use PSM=6 (uniform block).**

## Usage Examples

### Basic Usage (Auto-detect)

```python
from app.pdf_processor import PDFProcessor

processor = PDFProcessor("document.pdf", auto_detect=True)
result = await processor.extract_tables()
```

### Force OCR

```python
processor = PDFProcessor("scanned_document.pdf", force_ocr=True)
result = await processor.extract_tables()
```

### Custom OCR Configuration

```python
from app.pdf_processor import PDFProcessor
from app.ocr_processor import OCRConfig

# Create custom config
ocr_config = OCRConfig(
    dpi=300,
    denoise=True,
    deskew=True,
    contrast_enhance=True,
    min_confidence=50.0
)

# Use in processor (via OCRProcessor internally)
processor = PDFProcessor("document.pdf", force_ocr=True)
result = await processor.extract_tables()
```

## Election Form 20 Specific Configuration

For Indian election Form 20 documents, use these optimized settings:

```python
from app.ocr_processor import OCRConfig

election_config = OCRConfig(
    dpi=300,                    # High resolution for clarity
    denoise=True,               # Remove scan artifacts
    deskew=True,                # Correct any rotation
    contrast_enhance=True,      # Improve text visibility
    psm=6,                      # Uniform block (good for tables)
    min_confidence=50.0,         # Lower threshold for scanned docs
    use_easyocr_fallback=True   # Fallback for difficult pages
)
```

## Troubleshooting

### Tesseract Not Found

**Error:** `TesseractNotFoundError`

**Solution:**
1. Verify Tesseract is installed: `tesseract --version`
2. On Windows, set path in code:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

### Poppler Not Found

**Error:** `PDFInfoNotInstalledError` or `pdftoppm not found`

**Solution:**
1. Install Poppler (see System Requirements above)
2. On Windows, add Poppler `bin` folder to PATH
3. Verify: `pdftoppm -h` should work

### Low OCR Accuracy

**Solutions:**
1. Increase DPI (300-400 recommended)
2. Enable denoising and deskewing
3. Adjust contrast enhancement
4. Try different PSM modes (6 for tables, 3 for general text)
5. Use EasyOCR fallback for difficult pages

### Memory Issues with Large PDFs

**Solutions:**
1. Process pages in batches
2. Reduce DPI (200 instead of 300)
3. Disable some preprocessing steps
4. Use `pdf2image` with `thread_count=1` for lower memory

## Performance Tips

1. **DPI Settings:**
   - 200 DPI: Fast, lower quality
   - 300 DPI: Balanced (recommended)
   - 400 DPI: Slow, highest quality

2. **Preprocessing:**
   - Enable only what's needed
   - Denoising is most important for scanned docs
   - Deskewing helps with rotated scans

3. **Confidence Threshold:**
   - Lower (40-50%): More data, may include errors
   - Medium (60%): Balanced (recommended)
   - High (70%+): Fewer errors, may miss some text

4. **EasyOCR Fallback:**
   - Slower but sometimes more accurate
   - Use for difficult pages only

## Testing OCR Setup

Run this test to verify OCR is working:

```python
import pytesseract
from PIL import Image
import numpy as np

# Create a simple test image
img = Image.new('RGB', (200, 50), color='white')
# Add some text (you can use PIL ImageDraw)

# Test Tesseract
text = pytesseract.image_to_string(img)
print(f"OCR Result: {text}")

# Test with confidence
from pytesseract import Output
data = pytesseract.image_to_data(img, output_type=Output.DICT)
print(f"Confidence: {data['conf']}")
```

## Language Support

To use languages other than English:

1. Install language packs (see System Requirements)
2. Set language in config:
   ```python
   config = OCRConfig(language="hin")  # Hindi
   config = OCRConfig(language="eng+hin")  # Multiple languages
   ```

## API Integration

The OCR system is automatically integrated into the main API:

```python
# POST /api/upload
# The system automatically detects PDF type and uses OCR if needed

# Force OCR via query parameter (if added to API)
# POST /api/upload?force_ocr=true
```

## Output Format

Both text-based and OCR extractions return the same `TableData` structure:

```python
@dataclass
class TableData:
    headers: List[str]
    rows: List[List[str]]
    page_number: int
    extraction_method: str  # "pdfplumber" or "ocr"
    confidence_score: float  # 0.0 to 1.0
```

## Validation

The system includes automatic validation:

```python
from app.data_validator import ExtractionValidator

validator = ExtractionValidator()
report = validator.validate(tables, extraction_method="ocr")

print(f"Quality Grade: {report.quality_grade}")  # A, B, C, D, F
print(f"Confidence: {report.confidence_score:.2%}")
print(f"Issues: {len(report.issues)}")
```

## Best Practices

1. **Always use auto-detection first** - Let the system choose the best method
2. **Validate results** - Check confidence scores and validation reports
3. **Adjust for document type** - Election forms need different settings than general documents
4. **Monitor performance** - OCR is slower than text extraction, adjust DPI if needed
5. **Handle errors gracefully** - OCR can fail, have fallback strategies

## Support

For issues or questions:
1. Check this guide first
2. Review example code in `examples/ocr_usage_example.py`
3. Check validation reports for quality issues
4. Adjust OCR configuration based on document characteristics




