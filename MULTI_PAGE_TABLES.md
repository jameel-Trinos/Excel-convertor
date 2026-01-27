# Multi-Page Table Extraction

## Overview

The PDF to Excel converter now intelligently handles **multi-page tables** with sophisticated detection and filtering to produce clean Excel output that matches professional formatting standards.

## Key Features

### 1. **Smart Section Detection**

The system automatically identifies and categorizes different sections of your PDF table:

- **Title Rows**: Headers like "FORM 20 - FINAL RESULT SHEET - PART - I"
- **Header Rows**: Column names that define the table structure
- **Data Rows**: Actual tabular data
- **Section Headers**: Mid-table separators (e.g., "NOTAIVERIBA YTRAP")

### 2. **Duplicate Header Filtering**

Multi-page PDFs often repeat column headers on each page. The system:

✅ Detects duplicate headers appearing after page breaks
✅ Filters them out automatically
✅ Keeps only the first header row in the Excel output
✅ Uses 70% similarity matching to handle minor variations

### 3. **Section Header Removal**

Mid-table section headers (rows with 1-2 text cells and no numbers) are automatically filtered to keep only pure data rows.

## How It Works

### Detection Algorithm

```python
# 1. Detect title rows at the beginning
#    - Rows with ≤2 non-empty cells (merged appearance)
#    - Rows where all cells have the same value

# 2. Detect header rows after titles
#    - Rows with more text than numbers
#    - Rows with descriptive column names

# 3. Filter data rows
#    - Skip duplicate headers (70% match threshold)
#    - Skip section headers (1-2 cells, no numbers)
#    - Keep only genuine data rows
```

### Excel Output Structure

```
Row 1-4:  Title rows (merged across all columns)
Row 5:    Empty spacing row
Row 6:    Column headers (dark blue background)
Row 7+:   Clean data rows (no duplicate headers)
Last Row: TOTAL row with SUM formulas
```

## Example

### Input PDF (Multi-Page)

```
Page 1:
-------------------------------------------------
FORM 20 - FINAL RESULT SHEET - PART - I
GENERAL ELECTIONS TO TAMIL NADU LEGISLATIVE ASSEMBLY 2021
Assembly Constituency: 150 - JAYANKONDAM AC
Total Electors: 266,268

SI.NO | Polling Station | KANNAN KA | BALU K | ...
1     | 1               | 157       | 294    | ...
2     | 1(A)            | 179       | 311    | ...

Page 2:
-------------------------------------------------
NOTAIVERIBA YTRAP                    <- Section header (filtered)
SI.NO | Polling Station | KANNAN KA | BALU K | ...  <- Duplicate (filtered)
15    | 15              | 80        | 417    | ...
16    | 16              | 120       | 428    | ...
```

### Output Excel

```
Row 1: FORM 20 - FINAL RESULT SHEET - PART - I    [Merged]
Row 2: GENERAL ELECTIONS TO TAMIL NADU...          [Merged]
Row 3: Assembly Constituency: 150...               [Merged]
Row 4: Total Electors: 266,268                     [Merged]
Row 5: [Empty]
Row 6: SI.NO | Polling Station | KANNAN KA | ...   [Headers]
Row 7: 1     | 1               | 157       | ...   [Data]
Row 8: 2     | 1(A)            | 179       | ...   [Data]
Row 9: 15    | 15              | 80        | ...   [Data - no section header!]
Row 10: 16   | 16              | 120       | ...   [Data - no duplicate header!]
```

## Configuration

The detection thresholds can be adjusted in [pdf_processor.py](backend/app/pdf_processor.py):

```python
# Duplicate header matching threshold (default: 70%)
if (matches / total_checks) >= 0.7:
    return True

# Mid-table title detection (rows with ≤2 cells, no numbers)
if len(non_empty) <= 2:
    # ...filter logic
```

## Benefits

✅ **Clean Output**: No duplicate headers cluttering your data
✅ **Professional Format**: Matches government/official document standards
✅ **Automatic Processing**: No manual cleanup required
✅ **Multi-Page Support**: Handles PDFs with hundreds of pages
✅ **Intelligent Detection**: Uses heuristics to distinguish titles/headers/data

## Testing

The system has been tested with:
- Single-page tables
- Multi-page tables with repeating headers
- Tables with section headers
- Government election result PDFs
- Complex hierarchical table structures

## API Response

The extraction returns structured data:

```json
{
  "tables": [
    {
      "title_rows": [
        ["FORM 20 - FINAL RESULT SHEET - PART - I", "", ""],
        ["GENERAL ELECTIONS TO TAMIL NADU...", "", ""]
      ],
      "header_rows": [
        ["SI.NO", "Polling Station", "KANNAN KA (DMK)", "..."]
      ],
      "rows": [
        ["1", "1", "157", "294"],
        ["2", "1(A)", "179", "311"]
        // No duplicate headers in data!
      ],
      "page_number": 1
    }
  ]
}
```

## Related Files

- [pdf_processor.py](backend/app/pdf_processor.py) - Extraction and filtering logic
- [excel_creator.py](backend/app/excel_creator.py) - Excel generation
- [formatter.py](backend/app/formatter.py) - Styling and formatting
- [models.py](backend/app/models.py) - Data structures
