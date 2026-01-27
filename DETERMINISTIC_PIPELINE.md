# Deterministic Pipeline for Election Data Processing

## Overview

The deterministic pipeline is designed specifically for processing Indian Election Commission Form 20 (Final Result Sheets) with **absolute accuracy and reproducibility**. Unlike the AI-powered pipeline, this system follows strict rules and never infers table structure.

## Core Principles

### 1. **Row Boundaries Defined by Polling Station Number**
- Each row represents data for **one polling station**
- The "Polling Station" column value determines if a row is valid data
- NO heuristics, NO header detection logic
- Empty or non-numeric values in the Polling Station column → row is skipped

### 2. **Fixed Output Schema**
- Column names are preserved **exactly as they appear in the PDF**
- NO AI-based column standardization
- NO column merging or inference
- The schema from the first page defines the structure for all pages

### 3. **AI Used ONLY for Candidate → Party Mapping (Optional)**
- AI may identify which candidate belongs to which party
- Party names are already in the column headers: `"CANDIDATE NAME (PARTY)"`
- NO AI involvement in structure detection or data extraction

### 4. **Mandatory Vote Validation**
- Sum of all candidate votes + NOTA **MUST** equal "TOTAL VALID VOTES"
- If mismatch detected → warning logged (row still included)
- Missing or invalid vote counts → error reported

### 5. **Error on Validation Failures**
- Invalid polling station numbers → row skipped, warning logged
- Missing TOTAL VALID VOTES → error reported
- Vote sum mismatches → validation errors logged

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                  Deterministic Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. DeterministicParser                                      │
│     ├── Extract raw table from PDF (pdfplumber)             │
│     ├── Identify Polling Station column                     │
│     ├── Identify TOTAL VALID VOTES column                   │
│     ├── Filter rows by Polling Station value                │
│     └── Validate vote sums for each row                     │
│                                                              │
│  2. DeterministicExcelCreator                                │
│     ├── Preserve exact column names                         │
│     ├── Professional formatting (no AI processing)          │
│     ├── Add SUM formulas for totals                         │
│     └── Fixed column widths and row heights                 │
│                                                              │
│  3. API Endpoint: /api/convert-deterministic                 │
│     ├── Synchronous conversion                              │
│     ├── Returns Excel file directly                         │
│     └── Includes validation metadata in headers             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
backend/app/
├── deterministic_parser.py          # PDF parsing with validation
├── deterministic_excel_creator.py   # Excel generation
└── main.py                          # API endpoint
```

## API Usage

### Endpoint: `POST /api/convert-deterministic`

**Request:**
```bash
curl -X POST "http://localhost:8000/api/convert-deterministic" \
  -F "file=@form20.pdf" \
  -o result.xlsx
```

**Response:**
- **200 OK**: Excel file download
  - Headers include:
    - `X-Conversion-Mode: deterministic`
    - `X-Total-Rows: 293`
    - `X-Total-Columns: 21`

- **400 Bad Request**: Validation failed
  - Vote sum mismatch detected
  - Invalid PDF format
  - Missing required columns

- **500 Internal Server Error**: Conversion failed
  - PDF parsing error
  - Excel generation failed

## Schema for Form 20

The deterministic parser expects the following columns (in order):

1. **SL. NO.** - Serial number
2. **Polling Station** - Polling station number *(ROW BOUNDARY MARKER)*
3. **Candidate 1 (Party 1)** - Vote count
4. **Candidate 2 (Party 2)** - Vote count
5. ... *(variable number of candidates)*
6. **NOTA** - None of the above votes
7. **TOTAL VALID VOTES** - Sum validation column *(VALIDATION TARGET)*
8. **NO OF REJECTED VOTES** - Rejected votes
9. **TOTAL** - Total votes (valid + rejected)
10. **NO.OF TENDERED VOTES** - Tendered votes

### Column Detection Rules

- **Polling Station column**: Contains "polling" AND "station" (case-insensitive)
- **Total Valid Votes column**: Contains "total", "valid", and "vote" (case-insensitive)
- **Candidate columns**: All columns between Polling Station and TOTAL VALID VOTES (excluding NOTA)

## Validation Logic

### Row Validation

```python
# Step 1: Check Polling Station column
if not polling_station_value.isdigit():
    skip_row()  # Not a data row

# Step 2: Extract all vote columns
vote_columns = [
    col for col in headers
    if col not in ["SL. NO.", "Polling Station", "REJECTED", "TOTAL", "TENDER"]
]

# Step 3: Sum votes
calculated_sum = sum(int(row[col]) for col in vote_columns)

# Step 4: Compare to TOTAL VALID VOTES
expected_total = int(row["TOTAL VALID VOTES"])

if calculated_sum != expected_total:
    log_warning(f"Station {polling_station}: {calculated_sum} != {expected_total}")
    # Row still included, but warning logged
```

## Comparison with AI Pipeline

| Feature | Deterministic Pipeline | AI Pipeline |
|---------|----------------------|-------------|
| **Structure Detection** | Rule-based (Polling Station) | Heuristic (looks for patterns) |
| **Column Names** | Exact preservation | AI standardization |
| **Vote Validation** | ✅ Mandatory | ❌ Not performed |
| **Multi-page Handling** | Fixed schema from page 1 | AI merges different schemas |
| **Speed** | Fast (no AI calls) | Slower (multiple AI requests) |
| **Accuracy** | 100% deterministic | Varies (AI-dependent) |
| **Use Case** | Structured election data | General PDF tables |

## Error Handling

### Common Errors

1. **"Polling Station column not found"**
   - The PDF doesn't have a column with "Polling Station" in the header
   - **Solution**: Verify PDF format matches Form 20 structure

2. **"TOTAL VALID VOTES column not found"**
   - Missing the validation column
   - **Solution**: Check PDF has the complete schema

3. **"Vote validation failed: Station X: sum mismatch"**
   - Calculated vote sum doesn't match TOTAL VALID VOTES
   - **Solution**: Review PDF data quality, possible OCR errors

4. **"No tables found in PDF"**
   - pdfplumber couldn't extract any tables
   - **Solution**: Check PDF is not a scanned image (use OCR first)

## Testing

### Manual Test

```bash
# 1. Start the backend server
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 2. Test with a Form 20 PDF
curl -X POST "http://localhost:8000/api/convert-deterministic" \
  -F "file=@test_data/form20_sample.pdf" \
  -o output_deterministic.xlsx

# 3. Verify the Excel file
# - Check column names match PDF exactly
# - Verify row count matches polling stations
# - Confirm TOTAL row has correct SUM formulas
```

### Unit Test

```python
from app.deterministic_parser import DeterministicParser

# Test parser
parser = DeterministicParser("test.pdf")
headers, rows = parser.parse()

# Validate
assert "Polling Station" in headers
assert "TOTAL VALID VOTES" in headers
assert len(rows) > 0

# Check first row
assert rows[0][1].isdigit()  # Polling station number
```

## Advantages

### 1. **Reproducibility**
- Same PDF → Same Excel output (always)
- No AI randomness or model updates affecting results

### 2. **Speed**
- No AI API calls
- Direct table extraction → Excel conversion
- Typical processing: < 2 seconds for 300-row table

### 3. **Accuracy**
- Zero interpretation or inference
- Preserves exact data from PDF
- Validation ensures data integrity

### 4. **Transparency**
- Clear rules, no "black box" processing
- Easy to debug and verify
- Audit trail of validation errors

## Limitations

### 1. **Requires Structured PDFs**
- Only works with Form 20 format
- Assumes consistent column structure across pages

### 2. **No OCR**
- PDF must contain extractable text
- Scanned images won't work (pre-process with OCR)

### 3. **Limited Flexibility**
- Cannot handle variations in format
- Different election forms require separate parsers

## Future Enhancements

### Planned Features

1. **Configurable Schema**
   - Load schema from JSON config file
   - Support different Form variations (Form 20, Form 17C, etc.)

2. **Enhanced Validation**
   - Check sequential polling station numbers
   - Validate against expected turnout
   - Flag statistical anomalies

3. **Batch Processing**
   - Process multiple PDFs in parallel
   - Merge results into single Excel workbook

4. **Validation Report**
   - Generate separate report sheet with:
     - Validation errors
     - Summary statistics
     - Data quality metrics

## Migration from AI Pipeline

To migrate existing code to use deterministic pipeline:

**Before (AI Pipeline):**
```python
POST /api/upload
GET /api/progress/{task_id}  # Stream progress
GET /api/download/{task_id}   # Download result
```

**After (Deterministic):**
```python
POST /api/convert-deterministic  # Direct download, no task tracking
```

**Key Differences:**
- Synchronous (no background task)
- No progress streaming (conversion is fast)
- Direct file response
- No AI processing involved

## Support

For issues or questions:
- Check validation errors in server logs
- Verify PDF format matches Form 20 structure
- Test with sample PDF first: [sample_form20.pdf](test_data/)

---

**Last Updated**: January 2026
**Version**: 1.0.0
