# Column Filtering - Integration Guide

## System Integration

The column filtering service integrates seamlessly with the existing PDF to Excel converter system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                                                               │
│  1. Upload PDF → Get task_id                                │
│  2. Monitor progress (SSE)                                   │
│  3. Preview columns                                          │
│  4. Select columns to keep ← NEW FEATURE                    │
│  5. Download filtered Excel ← NEW FEATURE                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ PDF Processor    │  │ Column Filter    │ ← NEW SERVICE  │
│  │ - PDFPlumber     │  │ - Pandas         │                │
│  │ - Camelot        │  │ - Openpyxl       │                │
│  │ - Tabula         │  │ - Validation     │                │
│  └──────────────────┘  └──────────────────┘                │
│           │                      │                           │
│           ▼                      ▼                           │
│  ┌──────────────────────────────────────────┐              │
│  │         Excel Creator                     │              │
│  │         - Formatting                      │              │
│  │         - AI Enhancement                  │              │
│  └──────────────────────────────────────────┘              │
│                       │                                      │
│                       ▼                                      │
│  ┌──────────────────────────────────────────┐              │
│  │      OUTPUT_DIR                           │              │
│  │      - original.xlsx                      │              │
│  │      - filtered_20260121_143025.xlsx ← NEW│              │
│  └──────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Standard Conversion Flow (Existing)
```
1. User uploads PDF
   ↓
2. PDF Processor extracts tables
   ↓
3. Claude AI enhances (optional)
   ↓
4. Excel Creator generates Excel
   ↓
5. User downloads Excel
```

### Enhanced Flow with Column Filtering (New)
```
1. User uploads PDF
   ↓
2. PDF Processor extracts tables
   ↓
3. Claude AI enhances (optional)
   ↓
4. Excel Creator generates Excel
   ↓
5. User previews columns ← NEW
   ↓
6. User selects columns to keep ← NEW
   ↓
7. Column Filter creates filtered Excel ← NEW
   ↓
8. User downloads filtered Excel ← NEW
```

## API Endpoints Integration

### Existing Endpoints
- `POST /api/upload` - Upload PDF for conversion
- `GET /api/status/{task_id}` - Check conversion status
- `GET /api/progress/{task_id}` - Real-time progress (SSE)
- `GET /api/preview/{task_id}` - Preview extracted data
- `GET /api/download/{task_id}` - Download full Excel

### New Endpoints
- `POST /api/filter-columns` - Filter Excel to selected columns
- `GET /api/download-filtered/{timestamp}` - Download filtered Excel

## Usage Patterns

### Pattern 1: Full Excel Download (Existing)
```
User → Upload PDF → Wait for completion → Download full Excel
```

### Pattern 2: Filtered Excel Download (New)
```
User → Upload PDF → Wait for completion →
       Preview columns → Select columns →
       Filter Excel → Download filtered Excel
```

### Pattern 3: Multiple Filtered Versions (New)
```
User → Upload PDF → Wait for completion →
       Select columns A,B,C → Download filtered_v1.xlsx →
       Select columns D,E,F → Download filtered_v2.xlsx →
       Select columns G,H,I → Download filtered_v3.xlsx
```

## Frontend Integration Points

### 1. Column Selection UI
After conversion completes, show column selection:

```typescript
// Get available columns
const preview = await fetch(`/api/preview/${taskId}`);
const { headers } = await preview.json();

// Let user select columns
const selectedColumns = userSelectedColumns(headers);

// Filter
const response = await fetch('/api/filter-columns', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    task_id: taskId,
    columns: selectedColumns
  })
});

const { timestamp } = await response.json();

// Download
window.location.href = `/api/download-filtered/${timestamp}`;
```

### 2. Download Options
Provide two download buttons:

```typescript
// Option 1: Download full Excel (existing)
<Button onClick={() => downloadFull(taskId)}>
  Download Full Excel
</Button>

// Option 2: Download filtered Excel (new)
<Button onClick={() => showColumnSelector(taskId)}>
  Select Columns & Download
</Button>
```

## State Management

The column filtering feature uses the existing task storage:

```python
# Existing task storage
tasks: Dict[str, ConversionTask] = {}

# Task contains original Excel path
task = tasks[task_id]
original_file = task.output_file  # Used for filtering

# Filtered files are independent
filtered_file = f"filtered_{timestamp}.xlsx"
```

## File Storage

### Directory Structure
```
outputs/
├── abc123-def456.xlsx                  # Original conversion
├── filtered_20260121_143025.xlsx       # Filtered version 1
├── filtered_20260121_143512.xlsx       # Filtered version 2
└── filtered_20260121_144008.xlsx       # Filtered version 3
```

### Cleanup Policy
Filtered files follow the same cleanup policy as original files:
- Retained for 1 hour
- Removed by periodic cleanup task
- Can be manually deleted via `/api/task/{task_id}`

## Error Handling

### Existing Error Flow
```
PDF Upload → Validation → Conversion → Error handling
```

### New Error Scenarios
```
Column Filtering → Validation:
  - Task exists?
  - Task completed?
  - Columns specified?
  - Columns exist in Excel?
→ Error handling
```

### Error Messages
```python
# Task not found
{"detail": "Task not found"}

# Task not completed
{"detail": "Task not completed. Current status: processing"}

# No columns specified
{"detail": "No columns specified. Please provide at least one column name."}

# Invalid columns
{"detail": "Requested columns not found in Excel file: ['BadCol']. Available columns: ['Col1', 'Col2']"}
```

## Performance Considerations

### Original Conversion
- CPU-intensive (PDF extraction)
- AI API calls (Claude/OpenAI)
- Time: 30-60 seconds typical

### Column Filtering
- Lightweight (pandas filtering)
- No AI calls required
- Time: 1-3 seconds typical

### Recommendation
Column filtering is fast enough to be synchronous (no SSE needed).

## Security Considerations

### Existing Security
- File size limits (10MB)
- PDF validation
- File cleanup (1 hour retention)

### New Security Additions
- Column name validation
- Task ownership verification
- Timestamp-based file access

## Testing Integration

### Unit Tests
```python
# Test column_filter.py
def test_filter_columns():
    service = ColumnFilterService()
    filtered_file, metadata = service.filter_columns(
        input_file="test.xlsx",
        requested_columns=["Col1", "Col2"],
        output_dir="./test_output"
    )
    assert filtered_file.endswith(".xlsx")
    assert metadata["total_columns"] == 2
```

### Integration Tests
```python
# Test API endpoints
async def test_filter_api():
    # 1. Upload PDF
    task_id = await upload_pdf("test.pdf")

    # 2. Wait for completion
    await wait_for_completion(task_id)

    # 3. Filter columns
    response = await client.post(
        "/api/filter-columns",
        json={"task_id": task_id, "columns": ["Col1"]}
    )
    assert response.status_code == 200

    # 4. Download
    timestamp = response.json()["timestamp"]
    download = await client.get(f"/api/download-filtered/{timestamp}")
    assert download.status_code == 200
```

## Monitoring and Logging

### Log Messages
```python
# Filtering started
logger.info(f"Filtering columns for task {task_id}: {columns}")

# Filtering completed
logger.info(f"Column filtering completed: {filtered_file}")

# Errors
logger.error(f"Column filtering failed: {error}", exc_info=True)
```

### Metrics to Track
- Number of filter requests
- Average filter time
- Most commonly selected columns
- Error rate

## Migration Path

### Phase 1: Backend Deployment (Completed)
- ✓ Deploy column_filter.py
- ✓ Deploy updated models.py
- ✓ Deploy updated main.py
- ✓ Restart backend server

### Phase 2: Frontend Integration (Future)
- Add column selection UI
- Add filtered download button
- Update download flow
- Add error handling UI

### Phase 3: Optimization (Future)
- Cache filtered files
- Batch filtering
- Column presets
- User preferences

## Backwards Compatibility

The new feature is fully backwards compatible:

- ✓ Existing endpoints unchanged
- ✓ Existing data models unchanged
- ✓ Existing functionality preserved
- ✓ New endpoints are additive
- ✓ No breaking changes

Users can continue using the existing flow without any changes.
