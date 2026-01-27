# Frontend Integration - OCR Support

## ✅ Yes, It Works!

When you upload a PDF through the frontend, the system will:

1. **Automatically detect** if the PDF is text-based or image-based (scanned)
2. **Use the appropriate method**:
   - Text-based PDFs → `pdfplumber` (fast)
   - Image-based PDFs → `OCR` (pytesseract + preprocessing)
3. **Fallback to OCR** if pdfplumber finds no tables
4. **Show progress updates** via Server-Sent Events (SSE)
5. **Validate quality** and provide confidence scores

## How It Works

### Upload Flow

```
Frontend Upload → POST /api/upload
    ↓
Backend saves PDF file
    ↓
Background task starts (process_conversion)
    ↓
PDFProcessor created (auto_detect=True by default)
    ↓
PDF Type Detection
    ├─→ TEXT → pdfplumber extraction
    ├─→ IMAGE → OCR extraction
    └─→ MIXED → OCR extraction
    ↓
Progress updates sent via SSE
    ↓
Excel file created
    ↓
Task marked as completed
```

### Progress Messages You'll See

**For Text-based PDFs:**
- "Detecting PDF type..."
- "PDF type: text"
- "Extracting tables from PDF..."
- "Extracting tables from page X of Y..."
- "Merging tables from all pages..."
- "Validating extraction results..."
- "Extraction complete"

**For Image-based/Scanned PDFs:**
- "Detecting PDF type..."
- "PDF type: image"
- "Starting OCR extraction..."
- "Converting PDF pages to images..."
- "Processing page X of Y with OCR..."
- "Merging tables from all pages..."
- "Validating extraction results..."
- "Extraction complete"

**If pdfplumber finds nothing (fallback):**
- "No text tables found, trying OCR..."
- Then follows OCR messages above

## Prerequisites

### System Dependencies (Required)

Before uploading scanned PDFs, ensure these are installed:

**macOS:**
```bash
brew install tesseract poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr poppler-utils
```

**Windows:**
- Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
- Install Poppler from: https://github.com/oschwartz10612/poppler-windows/releases

### Verify Installation

Run the test script:
```bash
cd backend
python test_ocr_setup.py
```

## What Happens in the Frontend

### 1. Upload Request
```typescript
// Frontend sends PDF file
POST /api/upload
Response: { task_id, filename, size, message }
```

### 2. Progress Updates (SSE)
```typescript
// Frontend connects to progress stream
GET /api/progress/{task_id}
Events: { progress, status, message }
```

You'll see messages like:
- `"Detecting PDF type..."` (5%)
- `"PDF type: image"` (10%)
- `"Starting OCR extraction..."` (10%)
- `"Converting PDF pages to images..."` (10%)
- `"Processing page 1 of 5 with OCR..."` (20-80%)
- `"Merging tables from all pages..."` (85%)
- `"Validating extraction results..."` (95%)
- `"Extraction complete"` (100%)

### 3. Status Check
```typescript
GET /api/status/{task_id}
Response: { status, progress, message, output_file }
```

### 4. Download
```typescript
GET /api/download/{task_id}
Response: Excel file download
```

## Testing

### Test with Text-based PDF
1. Upload a PDF with extractable text
2. Should see: "PDF type: text"
3. Fast extraction with pdfplumber

### Test with Scanned PDF
1. Upload a scanned/image-based PDF (like election Form 20)
2. Should see: "PDF type: image"
3. OCR extraction will run
4. Progress will show OCR steps

### Test Fallback
1. Upload a PDF where pdfplumber finds no tables
2. Should see: "No text tables found, trying OCR..."
3. System automatically switches to OCR

## Error Handling

If OCR dependencies are missing, you'll see errors like:

- `TesseractNotFoundError` → Install Tesseract
- `PDFInfoNotInstalledError` → Install Poppler

The system will:
1. Log the error
2. Mark task as "failed"
3. Return error message in task status

## Performance

### Text-based PDFs
- **Speed**: Fast (seconds)
- **Method**: pdfplumber
- **Progress**: 10-80% (extraction)

### Image-based PDFs (OCR)
- **Speed**: Slower (minutes for large PDFs)
- **Method**: OCR with preprocessing
- **Progress**: 10-90% (OCR processing)
- **Factors**: DPI, page count, preprocessing steps

### Typical Times
- 1-page text PDF: ~2-5 seconds
- 1-page scanned PDF: ~10-30 seconds
- 10-page scanned PDF: ~2-5 minutes

## Quality Indicators

After extraction, check the validation:

```typescript
// In the extraction result
{
  extraction_method: "ocr" | "pdfplumber",
  confidence_score: 0.0-1.0,
  quality_grade: "A" | "B" | "C" | "D" | "F"
}
```

- **A/B**: Excellent/Good quality
- **C**: Acceptable (review recommended)
- **D/F**: Poor quality (manual review required)

## Frontend Code Example

The frontend doesn't need any changes! The existing code will work:

```typescript
// Upload
const formData = new FormData();
formData.append('file', pdfFile);
const response = await fetch('/api/upload', {
  method: 'POST',
  body: formData
});

// Progress (SSE)
const eventSource = new EventSource(`/api/progress/${taskId}`);
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.message); // Shows OCR progress messages
  updateProgressBar(data.progress);
};
```

## Troubleshooting

### OCR Not Working

1. **Check system dependencies:**
   ```bash
   python backend/test_ocr_setup.py
   ```

2. **Check logs:**
   ```bash
   # Backend logs will show:
   # - PDF type detection results
   # - OCR processing steps
   # - Any errors
   ```

3. **Verify PDF type:**
   - Upload a PDF
   - Check progress messages
   - Should see "PDF type: image" for scanned PDFs

### Slow Processing

- OCR is slower than text extraction
- Large PDFs (10+ pages) can take several minutes
- This is normal for OCR processing

### Low Quality Results

- Check confidence score in validation report
- Lower DPI or poor scan quality = lower confidence
- Consider rescanning at higher resolution

## Summary

✅ **Fully Integrated**: OCR works automatically with frontend uploads
✅ **Auto-Detection**: No frontend changes needed
✅ **Progress Updates**: Real-time OCR progress via SSE
✅ **Error Handling**: Graceful fallbacks and error messages
✅ **Quality Validation**: Confidence scores and quality grades

Just make sure system dependencies (Tesseract, Poppler) are installed, and it will work automatically!




