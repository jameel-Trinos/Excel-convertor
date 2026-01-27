# POST /convert Endpoint Documentation

## Overview

The `/convert` endpoint is a synchronous API that converts PDF files to Excel spreadsheets with Claude AI-powered intelligence. It processes the entire conversion in one request and returns the Excel file path along with detailed column metadata.

## Endpoint

```
POST /convert
```

## Request

### Content-Type
`multipart/form-data`

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | PDF file to convert (max 10MB) |

### Example Request (cURL)

```bash
curl -X POST http://localhost:8000/convert \
  -F "file=@election_results.pdf" \
  -H "Accept: application/json"
```

### Example Request (Python)

```python
import requests

with open('election_results.pdf', 'rb') as f:
    files = {'file': ('election_results.pdf', f, 'application/pdf')}
    response = requests.post('http://localhost:8000/convert', files=files)
    data = response.json()
    print(f"Excel file: {data['excel_file_path']}")
    print(f"Columns: {data['column_names']}")
```

### Example Request (JavaScript/Fetch)

```javascript
const formData = new FormData();
formData.append('file', pdfFile); // pdfFile is a File object

const response = await fetch('http://localhost:8000/convert', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log('Excel file:', data.excel_file_path);
console.log('Columns:', data.column_names);
```

## Response

### Success Response (200 OK)

```json
{
  "excel_file_path": "/path/to/outputs/abc123-xyz.xlsx",
  "column_names": [
    "S.No",
    "Candidate Name",
    "Party",
    "DMK",
    "AIADMK",
    "BJP",
    "Total Votes"
  ],
  "total_rows": 156,
  "total_columns": 7,
  "document_title": "FORM 20 - GENERAL ELECTIONS 2021",
  "party_columns": [
    "DMK",
    "AIADMK",
    "BJP"
  ],
  "ai_metadata": {
    "ai_enabled": true,
    "ai_provider": "anthropic",
    "ai_model_used": "claude-sonnet-4-20250514",
    "heading_detected": true,
    "heading_confidence": 0.95,
    "columns_standardized": true,
    "column_confidence": 0.92
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `excel_file_path` | string | Absolute path to the generated Excel file |
| `column_names` | array[string] | List of standardized column names from the Excel file |
| `total_rows` | integer | Total number of data rows (excluding title/header rows) |
| `total_columns` | integer | Total number of columns |
| `document_title` | string\|null | Extracted document title (Claude AI detected) |
| `party_columns` | array[string] | Columns identified as party vote columns |
| `ai_metadata` | object | Metadata about AI processing |

### AI Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `ai_enabled` | boolean | Whether AI processing was used |
| `ai_provider` | string | AI provider used ("anthropic" or "openai") |
| `ai_model_used` | string | Specific AI model used |
| `heading_detected` | boolean | Whether document heading was detected |
| `heading_confidence` | float | Confidence score for heading detection (0.0-1.0) |
| `columns_standardized` | boolean | Whether columns were standardized |
| `column_confidence` | float | Confidence score for column standardization (0.0-1.0) |

## Error Responses

### 400 Bad Request - Invalid File Type

```json
{
  "detail": "Only PDF files are accepted"
}
```

### 400 Bad Request - File Too Large

```json
{
  "detail": "File too large. Maximum size is 10MB"
}
```

### 400 Bad Request - No Tables Found

```json
{
  "detail": "No tables found in the PDF"
}
```

### 503 Service Unavailable - Missing API Key

```json
{
  "detail": "ANTHROPIC_API_KEY not configured. Claude AI is required for this endpoint."
}
```

### 500 Internal Server Error

```json
{
  "detail": "Conversion failed: <error message>"
}
```

## Features

### 1. Claude AI Integration

The endpoint uses **Anthropic Claude AI** for superior document analysis:

- **Document Heading Extraction**: Automatically detects and extracts the main document title
- **Column Standardization**: Intelligently merges tables with different column name variations
- **Party Name Normalization**: Standardizes Tamil Nadu political party names (DMK, AIADMK, BJP, etc.)

### 2. Party Column Identification

The endpoint automatically identifies columns that contain party-related data based on:
- Column names containing party keywords (DMK, AIADMK, BJP, Congress, etc.)
- Column names containing vote-related keywords (votes, candidate, party)

### 3. Excel Output Features

The generated Excel file includes:
- **Multi-row title extraction**: Preserves hierarchical title structure
- **Smart header detection**: Automatically identifies column headers
- **Professional formatting**: Borders, colors, proper column widths
- **Data quality**: Duplicate filtering, section header removal

## Configuration

### Required Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Required for this endpoint
```

### Optional Environment Variables

```bash
UPLOAD_DIR=./uploads            # Directory for temporary PDF uploads
OUTPUT_DIR=./outputs            # Directory for generated Excel files
MAX_FILE_SIZE=10485760          # Maximum file size in bytes (10MB)
```

## Processing Flow

1. **Upload & Validation**: PDF file is uploaded and validated
2. **Table Extraction**: Tables are extracted using multi-strategy approach (pdfplumber → camelot → tabula)
3. **Claude AI Analysis**:
   - Extract document heading from page text
   - Standardize column headers across all tables
   - Apply party name normalization
4. **Party Column Identification**: Identify columns containing party vote data
5. **Excel Generation**: Create professionally formatted Excel file
6. **Metadata Extraction**: Read Excel to extract actual column names and counts
7. **Response**: Return file path and comprehensive column metadata

## Usage Notes

1. **Synchronous Processing**: This endpoint blocks until conversion is complete. For large PDFs, use the `/api/upload` endpoint with SSE progress tracking instead.

2. **File Cleanup**: Uploaded PDFs are automatically deleted after processing. Excel files are retained in the output directory.

3. **Column Names**: The `column_names` array contains the **actual** column names from the generated Excel file, which may differ from the original PDF due to standardization.

4. **Party Columns**: The `party_columns` array is a subset of `column_names` containing only party-related columns, useful for UI rendering.

5. **File Path**: The `excel_file_path` is an absolute path on the server. Use this for accessing the file programmatically or serving it via a download endpoint.

## Example Use Case: UI Rendering

```javascript
// Fetch and display column metadata
const response = await fetch('/convert', {
  method: 'POST',
  body: formData
});

const { column_names, party_columns, total_rows } = await response.json();

// Render table headers
const headers = column_names.map(col => {
  const isPartyColumn = party_columns.includes(col);
  return {
    name: col,
    isParty: isPartyColumn,
    // Highlight party columns differently in UI
    className: isPartyColumn ? 'party-column' : 'regular-column'
  };
});

console.log(`Rendering table with ${total_rows} rows and ${column_names.length} columns`);
```

## Testing

### Using the Test Script

```bash
# Run the provided test script
python test_convert_endpoint.py path/to/your/file.pdf

# Or with custom API URL
python test_convert_endpoint.py path/to/your/file.pdf http://localhost:8000
```

### Using cURL

```bash
# Basic conversion
curl -X POST http://localhost:8000/convert \
  -F "file=@election_results.pdf" \
  -o response.json

# View response
cat response.json | jq '.'
```

## Performance

- **Small PDFs (1-5 pages)**: 5-15 seconds
- **Medium PDFs (5-20 pages)**: 15-45 seconds
- **Large PDFs (20+ pages)**: 45-120 seconds

Processing time depends on:
- PDF complexity and table structure
- Number of pages and tables
- Claude AI processing time
- Server resources

## See Also

- [CLAUDE.md](CLAUDE.md) - Project overview and development commands
- [ANTHROPIC_CONFIGURATION.md](ANTHROPIC_CONFIGURATION.md) - Claude API setup
- [PARTY_NORMALIZATION.md](PARTY_NORMALIZATION.md) - Party name standardization details
- [AI_FEATURES.md](AI_FEATURES.md) - General AI features documentation
