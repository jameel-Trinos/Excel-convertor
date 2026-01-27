# Column Filtering Feature

This document describes the column filtering service that allows users to create filtered Excel files containing only selected columns.

## Overview

The column filtering service enables users to:
- Select specific columns from a converted Excel file
- Preserve the order of columns as requested
- Generate a new professionally formatted Excel file
- Download the filtered file with a timestamped filename

## Architecture

### Backend Components

1. **ColumnFilterService** ([backend/app/column_filter.py](backend/app/column_filter.py))
   - Loads Excel files using pandas
   - Validates that requested columns exist
   - Filters data to include only selected columns
   - Writes new Excel file using openpyxl
   - Applies professional formatting (headers, borders, column widths)

2. **API Endpoints** ([backend/app/main.py](backend/app/main.py))
   - `POST /api/filter-columns` - Create filtered Excel file
   - `GET /api/download-filtered/{timestamp}` - Download filtered file

3. **Data Models** ([backend/app/models.py](backend/app/models.py))
   - `FilterColumnsRequest` - Request model with task_id and column list
   - `FilterColumnsResponse` - Response with filtered file metadata

## API Usage

### 1. Filter Columns

**Endpoint:** `POST /api/filter-columns`

**Request Body:**
```json
{
  "task_id": "abc123-def456-ghi789",
  "columns": ["Column Name 1", "Column Name 2", "Column Name 3"]
}
```

**Response:**
```json
{
  "filtered_file_path": "/path/to/filtered_20260121_143025.xlsx",
  "original_file": "/path/to/original.xlsx",
  "selected_columns": ["Column Name 1", "Column Name 2", "Column Name 3"],
  "total_columns": 3,
  "total_rows": 150,
  "columns_removed": 5,
  "timestamp": "20260121_143025"
}
```

**Error Responses:**
- `404` - Task not found
- `400` - Task not completed or no columns specified
- `400` - Requested columns don't exist in Excel file
- `500` - Internal server error

### 2. Download Filtered File

**Endpoint:** `GET /api/download-filtered/{timestamp}`

**Parameters:**
- `timestamp` - Timestamp from filter response (format: YYYYMMDD_HHMMSS)

**Response:** Excel file download

## File Naming Convention

Filtered files are named using the pattern:
```
filtered_<timestamp>.xlsx
```

Where `<timestamp>` is in the format `YYYYMMDD_HHMMSS`.

Example: `filtered_20260121_143025.xlsx`

## Excel Formatting

The filtered Excel files include professional formatting:

### Header Row
- **Background:** Dark blue (#1F4E78)
- **Font:** White, bold, 11pt
- **Alignment:** Center, wrapped text
- **Height:** 70px
- **Frozen:** Header row is frozen for scrolling

### Data Rows
- **Borders:** Thin borders on all cells
- **Alignment:** Left-aligned, vertically centered
- **Height:** 18px

### Column Widths
- Automatically adjusted based on content
- Minimum width: 15 characters
- Maximum width: 50 characters

## Usage Example

```python
import requests

# 1. First, convert a PDF to Excel (get task_id)
# ...

# 2. Filter columns from the converted Excel
response = requests.post(
    "http://localhost:8000/api/filter-columns",
    json={
        "task_id": "your-task-id",
        "columns": ["Polling Station", "Total Votes", "DMK Votes"]
    }
)

result = response.json()
timestamp = result["timestamp"]

# 3. Download the filtered file
download_url = f"http://localhost:8000/api/download-filtered/{timestamp}"
filtered_excel = requests.get(download_url)

with open("my_filtered_data.xlsx", "wb") as f:
    f.write(filtered_excel.content)
```

## Column Validation

The service validates that all requested columns exist in the source Excel file. If any column is missing, the request fails with a detailed error message:

```json
{
  "detail": "Requested columns not found in Excel file: ['Invalid Column']. Available columns: ['Column1', 'Column2', 'Column3']"
}
```

## Performance

- Uses pandas for efficient data loading and filtering
- Uses openpyxl for Excel writing and formatting
- Runs asynchronously to avoid blocking the API server
- File operations are thread-safe

## Limitations

- Column names must match exactly (case-sensitive)
- Requires a completed conversion task (task status must be "completed")
- Filtered files are stored in the OUTPUT_DIR alongside original conversions
- Subject to the same cleanup policies as original Excel files (1 hour retention)

## Testing

Run the test script to verify the service:

```bash
cd backend
python test_column_filter.py
```

For full integration testing:

1. Start the backend server
2. Upload and convert a PDF
3. Use the `/api/filter-columns` endpoint with the task_id
4. Download the filtered file using the returned timestamp

## Future Enhancements

Potential improvements:
- Column name fuzzy matching for typo tolerance
- Support for column reordering without filtering
- Batch filtering for multiple column sets
- Custom formatting options (colors, fonts, etc.)
- Preview endpoint for filtered data before download
