# Constituency Text Parser Implementation

## Overview

This implementation provides a text-based parser for constituency PDFs with structured entry format. It extracts entries from PDFs that have the following structure:

```
[Serial Number] [ID Number] [Text content]
[1] -Sub-area 1, [2] -Sub-area 2, etc.
```

## Features

### 1. Text-Based Entry Extraction
- Parses entries starting with two numbers (serial number and ID number)
- Handles special case for entries 1-9 where numbers may appear as "11", "22", "33" instead of "1 1", "2 2", "3 3"
- Extracts multi-line entries spanning 2-5 lines
- Separates location text from sub-areas marked with [n] markers

### 2. Header/Footer Filtering
- Automatically filters out common headers and footers:
  - "List of"
  - "Page Number"
  - Lines with only page numbers
  - "Total" and "Grand Total" lines

### 3. Structured Data Extraction
Each entry is parsed into:
- **Serial Number** (integer)
- **ID Number** (integer)
- **Main Location Text** (text before [1] marker)
- **Sub-areas** (all [n] - text patterns, separated by |)

### 4. Professional Excel Formatting
- Title row with merged cells and colored background
- Styled header row (blue background, white text, bold)
- Data rows with:
  - Alternating row colors for readability
  - Text wrapping enabled
  - Borders around all cells
  - Proper column widths (auto-adjusted based on content)
- Frozen header rows for easy scrolling

## Files Created/Modified

### New Files

1. **`backend/app/constituency_text_parser.py`**
   - Text-based parser for constituency PDFs
   - Handles entry extraction, header/footer filtering, and data cleaning
   - Main class: `ConstituencyTextParser`

### Modified Files

1. **`backend/app/constituency_processor.py`**
   - Added `use_text_parser` parameter to `extract_tables()` method
   - Added `_extract_with_text_parser()` method to use the text parser

2. **`backend/app/constituency_excel_creator.py`**
   - Added title row with merged cells and colored background
   - Enhanced data cell formatting with alternating row colors
   - Improved text wrapping and alignment

3. **`backend/app/main.py`**
   - Updated `process_conversion()` to use text parser for constituency conversions
   - Automatically enables text parser when using constituency processor

4. **`convert_constituency_pdf.py`** (new script)
   - Standalone script for converting constituency PDFs
   - Can be run directly from command line

## Usage

### Method 1: Using the API Endpoint

The constituency endpoint automatically uses the text parser:

```bash
curl -X POST "http://localhost:8000/api/constituency/upload" \
  -F "file=@AC001.pdf"
```

### Method 2: Using the Standalone Script

```bash
python convert_constituency_pdf.py AC001.pdf
```

Or with custom output directory:

```bash
python convert_constituency_pdf.py AC001.pdf ./outputs
```

### Method 3: Using Python Code

```python
import asyncio
from backend.app.constituency_processor import ConstituencyProcessor
from backend.app.constituency_excel_creator import ConstituencyExcelCreator

async def convert():
    processor = ConstituencyProcessor("AC001.pdf")
    result = await processor.extract_tables(use_text_parser=True)
    
    creator = ConstituencyExcelCreator()
    output_file = creator.create_from_tables(
        tables=result.tables,
        output_path="output.xlsx",
        source_filename="AC001.pdf"
    )
    print(f"Excel file created: {output_file}")

asyncio.run(convert())
```

## Entry Format Examples

### Input PDF Format

```
1 1 Panchayat Union Primary School, North Building
    [1] -Village (Ward-1), [2] -Colony (Ward-2)

2 2 Government High School, South Block
    [1] -Town Area (Ward-3), [2] -Rural Area (Ward-4)

11 11 Community Center, Main Hall
    [1] -Zone A, [2] -Zone B, [3] -Zone C
```

### Output Excel Format

| Sl.No | ID | Location | Areas |
|-------|----|----------|-------|
| 1 | 1 | Panchayat Union Primary School, North Building | [1] Village (Ward-1) \| [2] Colony (Ward-2) |
| 2 | 2 | Government High School, South Block | [1] Town Area (Ward-3) \| [2] Rural Area (Ward-4) |
| 11 | 11 | Community Center, Main Hall | [1] Zone A \| [2] Zone B \| [3] Zone C |

## Special Handling

### Entries 1-9 Format

For entries 1-9, the parser handles cases where numbers appear as double digits:

- "11" → Serial: 1, ID: 1
- "22" → Serial: 2, ID: 2
- "33" → Serial: 3, ID: 3
- etc.

This is detected by checking if the number is a double digit with the same digit repeated.

### Multi-line Entries

Entries can span multiple lines. The parser collects all lines until it detects the next entry start pattern.

### Sub-area Extraction

Sub-areas are extracted using regex pattern matching:
- Pattern: `\[(\d+)\]\s*-?\s*(.+?)(?=\s*\[|\s*$|,)`
- Handles formats like:
  - `[1] -Village`
  - `[1] Village`
  - `[1] -Village (Ward-1)`

## Excel Formatting Details

### Title Row
- Merged cells across all columns
- Light blue background (#D6E3F0)
- Bold, 14pt font
- Centered text

### Header Row
- Dark blue background (#366092)
- White text, bold, 10pt font
- Centered with text wrapping
- Borders on all cells

### Data Rows
- Alternating colors:
  - Even rows: White (#FFFFFF)
  - Odd rows: Light gray (#F2F2F2)
- Text wrapping enabled
- Center alignment
- Borders on all cells
- Auto-adjusted column widths (min 10, max 50)

### Frozen Panes
- Header rows (title + header) are frozen for easy scrolling

## Error Handling

The parser includes robust error handling:
- File not found errors
- PDF extraction errors
- Invalid entry format warnings
- Empty extraction warnings

All errors are logged with detailed information for debugging.

## Testing

To test the parser:

1. Place your PDF file (e.g., `AC001.pdf`) in the project root
2. Run the conversion script:
   ```bash
   python convert_constituency_pdf.py AC001.pdf
   ```
3. Check the output in `backend/outputs/AC001_converted.xlsx`

## Dependencies

Required Python packages (already in requirements.txt):
- `pypdf` or `pdfplumber` - PDF text extraction
- `pandas` - Data manipulation (if needed)
- `openpyxl` - Excel file creation and formatting
- `re` - Regular expressions (built-in)

## Notes

- The parser is designed specifically for constituency PDFs with the described format
- It may not work correctly for other PDF formats
- For best results, ensure the PDF has clear text (not scanned images)
- If the PDF is image-based, OCR may be required first

## Future Enhancements

Potential improvements:
1. Support for more entry formats
2. Better handling of OCR-extracted text
3. Configurable formatting options
4. Support for additional sub-area formats
5. Validation of extracted data




