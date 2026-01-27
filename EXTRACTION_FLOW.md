# PDF to Excel Extraction Flow

**Complete data flow showing Anthropic Claude integration**

---

## Overview

```
PDF Upload → Table Extraction → Claude AI Enhancement → Excel Generation → Download
```

---

## Detailed Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER UPLOADS PDF                                             │
│    Frontend: POST /api/upload                                   │
│    ↓                                                             │
│    Returns: task_id                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. PDF PROCESSING (Progress: 10-50%)                            │
│    Backend: PDFProcessor.extract_tables()                       │
│                                                                  │
│    Strategy 1: pdfplumber (standard extraction)                 │
│         ↓ (if fails)                                             │
│    Strategy 2: pdfplumber with strict lines                     │
│         ↓ (if fails)                                             │
│    Strategy 3: camelot-py                                       │
│         ↓ (if fails)                                             │
│    Strategy 4: tabula-py                                        │
│                                                                  │
│    Extracts:                                                     │
│    ✓ Title rows (merged cells)                                  │
│    ✓ Multi-row headers                                          │
│    ✓ Data rows                                                  │
│    ✓ Page text (for AI analysis)                               │
│                                                                  │
│    Features:                                                     │
│    ✓ Duplicate header filtering                                 │
│    ✓ Section header removal                                     │
│    ✓ OCR artifact cleaning                                      │
│    ✓ Cell text cleaning                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. VALIDATION (Progress: 52%)                                   │
│    Backend: PDFProcessor.validate_extraction_completeness()     │
│                                                                  │
│    Checks:                                                       │
│    ✓ All pages processed                                        │
│    ✓ Tables found on expected pages                             │
│    ✓ Row counts reasonable                                      │
│    ✓ Column consistency                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. AI PROCESSING - ANTHROPIC CLAUDE (Progress: 55-70%)         │
│    Backend: ClaudeProcessor (PRIMARY)                           │
│                                                                  │
│    ┌───────────────────────────────────────────────────────┐   │
│    │ Try Claude First ✓ ACTIVE                             │   │
│    │ Model: claude-3-5-sonnet-20241022                     │   │
│    │                                                        │   │
│    │ Step 4a: Extract Document Heading (60%)               │   │
│    │   Input: First page text                              │   │
│    │   Prompt: "Extract the main document heading..."      │   │
│    │   Output: "FORM 20 - FINAL RESULT SHEET\n            │   │
│    │            GENERAL ELECTIONS 2021"                     │   │
│    │   Confidence: 0.95                                     │   │
│    │                                                        │   │
│    │ Step 4b: Standardize Column Headers (65%)             │   │
│    │   Input: All table headers from all pages             │   │
│    │   Prompt: "Map these column headers..."               │   │
│    │   Output: {                                            │   │
│    │     "Polling Station": ["Station", "Polling No."],    │   │
│    │     "Candidate A": ["A Votes", "Candidate A"],        │   │
│    │     "NOTA": ["NOTA", "None of the Above"]             │   │
│    │   }                                                    │   │
│    │   Confidence: 0.90                                     │   │
│    │                                                        │   │
│    │ Features:                                              │   │
│    │   ✓ Multi-line heading preservation                   │   │
│    │   ✓ Intelligent column matching                       │   │
│    │   ✓ Response caching (cost optimization)              │   │
│    │   ✓ Low temperature (0.3) for consistency             │   │
│    └───────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│    ┌───────────────────────────────────────────────────────┐   │
│    │ Fallback: OpenAI GPT (if Claude unavailable)         │   │
│    │ Model: gpt-4o-mini                                    │   │
│    │ Same features as Claude                               │   │
│    └───────────────────────────────────────────────────────┘   │
│                              ↓                                   │
│    ┌───────────────────────────────────────────────────────┐   │
│    │ Basic Mode (if no AI keys)                            │   │
│    │ Uses first table headers as-is                        │   │
│    └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. EXCEL GENERATION (Progress: 70-90%)                         │
│    Backend: ExcelCreator.create_from_tables()                  │
│                                                                  │
│    Step 5a: Create Workbook                                     │
│    ┌─────────────────────────────────────────┐                 │
│    │ Row 1-2: TITLE SECTION                  │                 │
│    │   • Uses AI-detected heading            │                 │
│    │   • Merged across all columns           │                 │
│    │   • Font: Bold, 14pt                    │                 │
│    │   • Light blue background               │                 │
│    │   • Height: 25px                        │                 │
│    ├─────────────────────────────────────────┤                 │
│    │ Row 3: EMPTY (spacing)                  │                 │
│    ├─────────────────────────────────────────┤                 │
│    │ Row 4-6: HEADERS                        │                 │
│    │   • Uses AI-standardized column names   │                 │
│    │   • Dark blue background (#4472C4)      │                 │
│    │   • White text, bold, 10pt              │                 │
│    │   • wrap_text=True                      │                 │
│    │   • Height: 70px                        │                 │
│    │   • Width: 16 chars per column          │                 │
│    ├─────────────────────────────────────────┤                 │
│    │ Row 7+: DATA ROWS                       │                 │
│    │   • Merged from all pages               │                 │
│    │   • Mapped to standard columns          │                 │
│    │   • Centered alignment                  │                 │
│    │   • Thin borders on all cells           │                 │
│    │   • Height: 18px per row                │                 │
│    │   • Number formatting: #,##0            │                 │
│    ├─────────────────────────────────────────┤                 │
│    │ Last Row: TOTAL ROW                     │                 │
│    │   • SUM formulas for numeric columns    │                 │
│    │   • Bold text                           │                 │
│    │   • Light blue background               │                 │
│    └─────────────────────────────────────────┘                 │
│                                                                  │
│    Step 5b: Apply Professional Formatting                       │
│    ExcelFormatter methods:                                      │
│    ✓ set_fixed_column_widths(default=16)                       │
│    ✓ set_row_heights(header=70, data=18)                       │
│    ✓ format_header_row(blue bg, white text)                    │
│    ✓ format_data_cells(borders, center align)                  │
│    ✓ apply_number_formatting(thousand separators)              │
│    ✓ freeze_panes(header row)                                  │
│                                                                  │
│    Step 5c: Intelligent Table Merging                           │
│    If AI column mapping available:                              │
│    • Maps variant column names to standard names                │
│    • Merges data from multiple pages into single table          │
│    • Handles column count differences                           │
│    Else:                                                         │
│    • Uses first table's headers                                 │
│    • Normalizes row lengths                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. SAVE & COMPLETE (Progress: 100%)                            │
│    Backend: workbook.save(output_path)                         │
│    ↓                                                             │
│    Frontend can now:                                            │
│    • Preview: GET /api/preview/{task_id}                       │
│    • Download: GET /api/download/{task_id}                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## AI Processing Details

### When Claude is Active

**Progress Messages:**
```
55% - "Running AI analysis..."
60% - "Claude AI: Detecting document heading..."
65% - "Claude AI: Standardizing columns..."
```

**Log Output:**
```
INFO:app.main:Claude AI processing enabled for task abc123
INFO:app.claude_processor:Claude AI processor initialized with model: claude-3-5-sonnet-20241022
INFO:app.claude_processor:Claude detected heading: 'FORM 20 - FINAL RESULT SHEET' (confidence: 0.95)
INFO:app.claude_processor:Claude standardized 8 columns (confidence: 0.90)
INFO:app.excel_creator:Creating Excel file with AI-enhanced formatting
```

**API Calls Made:**
1. **Heading Extraction:**
   - Endpoint: `https://api.anthropic.com/v1/messages`
   - Input tokens: ~500
   - Output tokens: ~50
   - Cost: ~$0.002

2. **Column Standardization:**
   - Endpoint: `https://api.anthropic.com/v1/messages`
   - Input tokens: ~1000
   - Output tokens: ~200
   - Cost: ~$0.006

**Total Time:** ~2-3 seconds for AI processing

### When OpenAI Fallback is Used

**Progress Messages:**
```
60% - "OpenAI: Detecting document heading..."
65% - "OpenAI: Standardizing columns..."
```

**Log Output:**
```
INFO:app.main:OpenAI processing enabled for task abc123 (Claude unavailable)
```

### When No AI is Available

**Progress Messages:**
```
55% - "Running AI analysis..."
70% - "Creating Excel file..."
```

**Log Output:**
```
INFO:app.main:AI processing disabled for task abc123 (no API keys found)
INFO:app.excel_creator:AI processing skipped (disabled or no page text)
```

**Excel Output:**
- Title: "Data extracted from: filename.pdf"
- Headers: First table's headers (no standardization)

---

## Quality Checkpoints

Throughout the flow, quality checks ensure accuracy:

### Checkpoint 1: PDF Validation (Upload)
```python
# utils.py: validate_pdf_file()
✓ File size < MAX_FILE_SIZE
✓ File extension is .pdf
✓ PDF is readable
```

### Checkpoint 2: Extraction Validation (Progress 52%)
```python
# pdf_processor.py: validate_extraction_completeness()
✓ Expected page count matches
✓ Tables found on all pages
✓ Row counts reasonable
✓ Column consistency across pages
✓ No completely empty tables
```

### Checkpoint 3: AI Response Validation
```python
# claude_processor.py
✓ Response is valid JSON (for column mapping)
✓ Heading is non-empty string
✓ Column mapping has valid structure
✓ Confidence scores in range [0.0, 1.0]
```

### Checkpoint 4: Excel Quality Check (Optional)
```python
# quality_checker.py
✓ Column widths set (not default 8.43)
✓ Row heights set (not default 15)
✓ Formulas have no errors
✓ Borders applied to all cells
✓ Data completeness verified
```

### Checkpoint 5: Formula Validation (Optional)
```bash
# recalc.py
python backend/recalc.py output.xlsx
✓ All formulas recalculate successfully
✓ No #REF!, #DIV/0!, or other errors
```

---

## Performance Metrics

**Typical conversion times** (10-page election form PDF):

| Stage | Time | Notes |
|-------|------|-------|
| Upload | <1s | File transfer |
| PDF Processing | 5-10s | Multi-strategy extraction |
| Validation | <1s | Quality checks |
| Claude AI | 2-3s | Heading + column standardization |
| Excel Generation | 1-2s | Formatting + formulas |
| **Total** | **9-16s** | End-to-end |

**Cost breakdown** (per PDF):
- Claude API calls: ~$0.01
- Server compute: ~$0.001
- **Total cost: ~$0.011 per PDF**

---

## Error Handling

### Extraction Errors
```python
# If all extraction strategies fail:
ValueError: "No tables found in the PDF"
→ Returns 400 error to frontend
→ User sees: "Could not extract tables from PDF"
```

### AI Processing Errors
```python
# If Claude API fails:
AnthropicError: "Rate limit exceeded"
→ Falls back to OpenAI
→ If OpenAI also fails:
→ Uses basic mode (no AI features)
→ Conversion continues successfully
```

### Formula Errors
```python
# If SUM formula has invalid range:
→ Excel shows #REF! error
→ Quality checker detects it
→ recalc.py reports the error
```

---

## Monitoring & Debugging

### Check Current Configuration
```bash
# View which AI processor is configured
grep -E "^(ANTHROPIC|OPENAI)" backend/.env

# Expected:
# ANTHROPIC_API_KEY=sk-ant-...  ← PRIMARY
# OPENAI_API_KEY=sk-proj-...    ← FALLBACK
```

### Monitor Conversion in Real-Time
```bash
# Watch backend logs
docker-compose logs -f backend

# Or if running directly
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000 --log-level info
```

### Debug Specific Task
```bash
# Check task status
curl http://localhost:8000/api/status/{task_id}

# Stream progress events
curl http://localhost:8000/api/progress/{task_id}
```

---

## Summary

The PDF to Excel extraction flow with Anthropic Claude provides:

✅ **Multi-strategy extraction** for maximum accuracy
✅ **Claude AI enhancement** for superior document understanding
✅ **Intelligent column mapping** across multi-page tables
✅ **Professional Excel formatting** with fixed widths and proper heights
✅ **Quality validation** at every checkpoint
✅ **Automatic fallback** if AI unavailable
✅ **Cost-effective** (~$0.01 per PDF)
✅ **Fast processing** (9-16 seconds end-to-end)

**Current status: ✓ Fully operational with Claude as primary AI processor**
