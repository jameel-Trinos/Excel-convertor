# OCR Quick Reference

## Quick Start

### 1. Install System Dependencies

**macOS:**
```bash
brew install tesseract poppler
```

**Ubuntu:**
```bash
sudo apt-get install tesseract-ocr poppler-utils
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Test Setup

```bash
python test_ocr_setup.py
```

## Common Usage Patterns

### Auto-detect PDF Type
```python
from app.pdf_processor import PDFProcessor

processor = PDFProcessor("document.pdf", auto_detect=True)
result = await processor.extract_tables()
```

### Force OCR for Scanned PDFs
```python
processor = PDFProcessor("scanned.pdf", force_ocr=True)
result = await processor.extract_tables()
```

### Get Detection Info
```python
from app.pdf_detector import PDFTypeDetector

detector = PDFTypeDetector()
info = detector.detect("document.pdf")
print(f"Type: {info.pdf_type.value}, Confidence: {info.confidence:.2%}")
```

### Validate Results
```python
from app.data_validator import ExtractionValidator

validator = ExtractionValidator()
report = validator.validate(result.tables, "ocr")
print(f"Grade: {report.quality_grade}, Confidence: {report.confidence_score:.2%}")
```

## Configuration Presets

### Election Form 20 (Recommended)
```python
from app.ocr_processor import OCRConfig

config = OCRConfig(
    dpi=300,
    denoise=True,
    deskew=True,
    contrast_enhance=True,
    psm=6,
    min_confidence=50.0,
    use_easyocr_fallback=True
)
```

### High Quality (Slow)
```python
config = OCRConfig(
    dpi=400,
    denoise=True,
    deskew=True,
    contrast_enhance=True,
    binarize=True,
    min_confidence=70.0
)
```

### Fast (Lower Quality)
```python
config = OCRConfig(
    dpi=200,
    denoise=False,
    deskew=False,
    contrast_enhance=False,
    min_confidence=40.0
)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `TesseractNotFoundError` | Install Tesseract: `brew install tesseract` (macOS) or `sudo apt-get install tesseract-ocr` (Ubuntu) |
| `PDFInfoNotInstalledError` | Install Poppler: `brew install poppler` (macOS) or `sudo apt-get install poppler-utils` (Ubuntu) |
| Low OCR accuracy | Increase DPI to 300-400, enable denoise/deskew, try PSM=6 |
| Slow processing | Reduce DPI to 200, disable some preprocessing steps |
| Memory errors | Process pages in batches, reduce DPI |

## Output Structure

```python
result.tables[0].extraction_method  # "pdfplumber" or "ocr"
result.tables[0].confidence_score  # 0.0 to 1.0
result.tables[0].headers          # List of column headers
result.tables[0].rows              # List of data rows
```

## Quality Grades

- **A**: Excellent (≥95% confidence, no errors)
- **B**: Good (≥85% confidence, ≤1 error)
- **C**: Acceptable (≥70% confidence, ≤3 errors)
- **D**: Poor (≥50% confidence)
- **F**: Very Poor (<50% confidence or critical errors)

## File Locations

- **Main processor**: `app/pdf_processor.py`
- **OCR processor**: `app/ocr_processor.py`
- **Table parser**: `app/table_parser.py`
- **PDF detector**: `app/pdf_detector.py`
- **Data validator**: `app/data_validator.py`
- **Examples**: `examples/ocr_usage_example.py`
- **Setup guide**: `OCR_SETUP.md`
- **Full summary**: `OCR_IMPLEMENTATION_SUMMARY.md`

## API Endpoints

- `POST /api/upload` - Upload PDF (auto-detects type)
- `GET /api/status/{task_id}` - Check status
- `GET /api/progress/{task_id}` - Real-time progress
- `GET /api/preview/{task_id}` - Preview data
- `GET /api/download/{task_id}` - Download Excel

## Key Features

✅ Automatic PDF type detection
✅ OCR with preprocessing (denoise, deskew, contrast)
✅ Election Form 20 specialized parsing
✅ Quality validation and confidence scoring
✅ EasyOCR fallback support
✅ Common OCR error correction
✅ Same output format for text and OCR

## Support

- See `OCR_SETUP.md` for detailed setup instructions
- See `OCR_IMPLEMENTATION_SUMMARY.md` for architecture details
- See `examples/ocr_usage_example.py` for code examples
- Run `python test_ocr_setup.py` to verify installation




