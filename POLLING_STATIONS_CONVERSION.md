# Polling Stations PDF to Excel Converter

This script converts structured polling station PDF documents to professionally formatted Excel files.

## Features

- **Table Extraction**: Uses pdfplumber to extract tabular data from PDF
- **Multi-page Support**: Handles PDFs spanning multiple pages (44+ pages)
- **Data Parsing**: Extracts:
  - Serial Number
  - Polling Station Number (ID)
  - Location and Building Name
  - Polling Areas (with [1], [2], etc. markers)
  - Polling Station Type (ALL VOTERS)
- **Professional Formatting**:
  - Title row with merged cells
  - Styled header row (blue background, white text)
  - Alternating row colors for readability
  - Text wrapping enabled
  - Borders on all cells
  - Frozen header row
  - Proper column widths

## Usage

### Basic Usage

```bash
python convert_polling_stations.py <pdf_path>
```

### Example

```bash
python convert_polling_stations.py AC001.pdf
```

If no PDF path is provided, the script will look for `AC001.pdf` in the current directory.

## Output

The script creates an Excel file in `backend/outputs/` directory with the format:
- Filename: `{pdf_name}_converted.xlsx`
- Example: `AC001_converted.xlsx`

## Requirements

The script uses the following packages (already in `requirements.txt`):
- `pdfplumber` - PDF table extraction
- `openpyxl` - Excel file creation and formatting

## PDF Structure Expected

The script expects PDFs with the following structure:

| Sl.No | Polling station No. | Location and name of building | Polling Areas | Polling Station Type |
|-------|---------------------|-------------------------------|---------------|---------------------|
| 1 | 1 | Panchayat Union Primary School... | [1] -Village (Ward-1), [2] -Colony (Ward-2) | ALL VOTERS |
| 2 | 2 | Government Higher Sec School... | [1] -Area (Ward-1) | ALL VOTERS |

## How It Works

1. **PDF Reading**: Opens PDF using pdfplumber
2. **Table Extraction**: Extracts tables from all pages using multiple strategies:
   - Lines strict (for tables with clear borders)
   - Lines (more lenient)
   - Default extraction (fallback)
3. **Data Parsing**: 
   - Identifies header rows
   - Extracts data rows from all pages
   - Parses polling areas with [n] markers
   - Handles special cases (entries 1-9 with "11", "22" format)
4. **Excel Creation**:
   - Creates formatted Excel workbook
   - Adds title section
   - Formats headers and data
   - Sets column widths and row heights
   - Freezes header row

## Error Handling

The script handles:
- Missing PDF files
- Empty or invalid PDFs
- Multi-page documents
- Header row detection
- Missing or malformed data

## Output Format

The Excel file includes:
- **Title Row**: Merged across all columns with document title
- **Header Row**: 
  - Sl.No
  - Polling Station No.
  - Location and Name of Building
  - Polling Areas
  - Polling Station Type
- **Data Rows**: All extracted entries with proper formatting
- **Styling**: Professional appearance with borders, colors, and proper alignment

## Notes

- The script automatically handles entries 1-9 that may have numbers formatted as "11", "22", etc.
- Polling areas are extracted and formatted with [n] markers preserved
- All text is cleaned and normalized
- Column widths are optimized for readability




