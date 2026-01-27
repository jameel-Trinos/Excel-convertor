# API Quick Reference - Column Filtering

## Endpoints

### 1. Filter Columns
Create a filtered Excel file with selected columns.

**POST** `/api/filter-columns`

**Request:**
```json
{
  "task_id": "string",
  "columns": ["column1", "column2", "column3"]
}
```

**Response (200):**
```json
{
  "filtered_file_path": "string",
  "original_file": "string",
  "selected_columns": ["string"],
  "total_columns": 0,
  "total_rows": 0,
  "columns_removed": 0,
  "timestamp": "string"
}
```

**Errors:**
- `404` - Task not found
- `400` - Task not completed / Invalid columns
- `500` - Server error

---

### 2. Download Filtered File
Download the filtered Excel file.

**GET** `/api/download-filtered/{timestamp}`

**Parameters:**
- `timestamp` (path) - Timestamp from filter response (YYYYMMDD_HHMMSS)

**Response (200):**
- Excel file download

**Errors:**
- `404` - File not found

---

## cURL Examples

### Filter Columns
```bash
curl -X POST http://localhost:8000/api/filter-columns \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "abc123-def456",
    "columns": ["Column 1", "Column 2", "Column 3"]
  }'
```

### Download Filtered File
```bash
curl -O http://localhost:8000/api/download-filtered/20260121_143025
```

---

## Python Example

```python
import requests

# Filter columns
response = requests.post(
    "http://localhost:8000/api/filter-columns",
    json={
        "task_id": "abc123-def456",
        "columns": ["Column 1", "Column 2"]
    }
)

result = response.json()
timestamp = result["timestamp"]

# Download
download_response = requests.get(
    f"http://localhost:8000/api/download-filtered/{timestamp}"
)

with open("filtered.xlsx", "wb") as f:
    f.write(download_response.content)
```

---

## Complete Workflow

```
1. Upload PDF
   POST /api/upload
   → task_id

2. Wait for completion
   GET /api/status/{task_id}
   → status: "completed"

3. Get available columns (optional)
   GET /api/preview/{task_id}
   → headers: ["Col1", "Col2", "Col3", ...]

4. Filter to desired columns
   POST /api/filter-columns
   → timestamp

5. Download filtered file
   GET /api/download-filtered/{timestamp}
   → filtered Excel file
```
