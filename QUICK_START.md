# Quick Start: POST /convert Endpoint

## Setup (One-time)

1. **Set API Key** in `/backend/.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

2. **Start Backend**:
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

## Usage Examples

### cURL
```bash
curl -X POST http://localhost:8000/convert \
  -F "file=@myfile.pdf"
```

### Python
```python
import requests

with open('myfile.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/convert',
        files={'file': f}
    )

data = response.json()
print(f"Excel: {data['excel_file_path']}")
print(f"Columns: {data['column_names']}")
print(f"Party columns: {data['party_columns']}")
```

### JavaScript/Fetch
```javascript
const formData = new FormData();
formData.append('file', pdfFile);

const response = await fetch('http://localhost:8000/convert', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log('Columns:', data.column_names);
console.log('Party columns:', data.party_columns);
```

### Test Script
```bash
python test_convert_endpoint.py path/to/file.pdf
```

## Response Structure

```json
{
  "excel_file_path": "/path/to/output.xlsx",
  "column_names": ["Col1", "Col2", "..."],
  "total_rows": 156,
  "total_columns": 10,
  "document_title": "Document Title",
  "party_columns": ["DMK", "AIADMK"],
  "ai_metadata": { ... }
}
```

## Key Features

- ✅ Claude AI-powered extraction
- ✅ Party column identification
- ✅ Document heading detection
- ✅ Column standardization
- ✅ Tamil Nadu party name normalization
- ✅ Professional Excel formatting

## Documentation

- Full API Docs: [CONVERT_ENDPOINT.md](CONVERT_ENDPOINT.md)
- Implementation: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- Interactive API: http://localhost:8000/docs
