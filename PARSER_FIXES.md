# Constituency Parser Fixes and Debugging Guide

## Issues Fixed

### 1. Improved Entry Detection
- **Problem**: Regex patterns were too strict and missed entries with different spacing
- **Fix**: Added multiple pattern matching strategies:
  - Pattern 1: Two separate numbers with spaces (`1 1 text`)
  - Pattern 2: Double digit format (`11 text` for entries 1-9)
  - Better handling of continuation lines

### 2. Enhanced Sub-Area Extraction
- **Problem**: Sub-areas weren't being extracted correctly
- **Fix**: 
  - Multiple regex patterns to handle different formats:
    - `[n] -text` (with dash)
    - `[n] text` (without dash)
    - `[n]text` (no space)
  - Better text cleaning and deduplication
  - Sorted by area number

### 3. Better Text Extraction
- **Problem**: PDF text extraction might fail for some PDFs
- **Fix**: 
  - Fallback to word-based extraction if text extraction fails
  - Better line cleaning and normalization
  - Improved handling of empty lines

### 4. Improved Header/Footer Filtering
- **Problem**: Too aggressive filtering was removing valid data
- **Fix**: 
  - More specific patterns that only match standalone headers/footers
  - Preserves lines that might be part of entries
  - Better logging to see what's being filtered

### 5. Enhanced Number Parsing
- **Problem**: Error handling for invalid numbers
- **Fix**: 
  - Try-catch blocks around number parsing
  - Better validation for double-digit entries (1-9 only)
  - Default values with warnings instead of crashes

## Debugging Your PDF

### Step 1: Run the Debug Script

Use the debug script to see exactly what's being extracted:

```bash
python debug_constituency_parser.py AC001.pdf
```

This will show you:
1. Raw text extracted from PDF
2. Filtered lines (after removing headers/footers)
3. Parsed entries with all fields
4. Table format preview

### Step 2: Check the Logs

The parser now includes detailed logging. Check the output for:
- How many lines were extracted
- What entries were found
- Any warnings about number parsing
- Sample entries to verify correctness

### Step 3: Verify Entry Format

Make sure your PDF entries follow this format:

```
[Serial Number] [ID Number] [Location Text]
[1] -Sub-area 1, [2] -Sub-area 2, etc.
```

Examples:
```
1 1 Panchayat Union Primary School, North Building
    [1] -Village (Ward-1), [2] -Colony (Ward-2)

2 2 Government High School
    [1] -Town Area, [2] -Rural Area

11 11 Community Center
    [1] -Zone A, [2] -Zone B
```

### Step 4: Common Issues and Solutions

#### Issue: Entries not being detected
**Solution**: Check if the entry starts with two numbers. The parser looks for:
- `1 1 text` (two numbers with space)
- `11 text` (double digit for entries 1-9)

#### Issue: Location text is empty
**Solution**: Make sure there's text before the first `[1]` marker. The location is everything before the first sub-area marker.

#### Issue: Sub-areas not extracted
**Solution**: Check the format of sub-areas. They should be:
- `[1] -text` or `[1] text` or `[1]text`
- Multiple sub-areas can be on the same line or different lines

#### Issue: Numbers are wrong
**Solution**: For entries 1-9, if numbers appear as "11", "22", etc., they'll be parsed as "1 1", "2 2". For entries 10+, use normal format like "10 10" or "11 11".

## Testing the Parser

### Test with Your PDF

1. **Run the debug script**:
   ```bash
   python debug_constituency_parser.py your_file.pdf
   ```

2. **Check the output**:
   - Look at the "First 20 lines" to see raw extraction
   - Check "First 20 filtered lines" to see what remains
   - Review "Parsed Entries" to verify correctness

3. **Compare with Excel output**:
   ```bash
   python convert_constituency_pdf.py your_file.pdf
   ```
   Then open the Excel file and compare with the debug output

### Expected Output Format

The parser should extract:
- **Sl.No**: Serial number (integer)
- **ID**: ID number (integer)
- **Location**: Main location text (before [1] marker)
- **Areas**: All sub-areas separated by ` | `

Example output:
```
Sl.No: 1
ID: 1
Location: Panchayat Union Primary School, North Building
Areas: [1] Village (Ward-1) | [2] Colony (Ward-2)
```

## If Data is Still Mismatched

### 1. Check PDF Text Extraction

The PDF might have formatting issues. Try:
- Opening the PDF in a text editor to see raw text
- Checking if the PDF is image-based (needs OCR)
- Verifying the text is selectable in the PDF viewer

### 2. Verify Entry Format

Make sure entries follow the expected format. The parser expects:
- Entry starts with two numbers
- Location text comes after the numbers
- Sub-areas are marked with `[n]`

### 3. Adjust Patterns (Advanced)

If your PDF has a different format, you may need to modify the regex patterns in `constituency_text_parser.py`:

- `pattern1`: For entries like "1 1 text"
- `pattern2`: For entries like "11 text" (entries 1-9)
- `sub_area_pattern`: For extracting sub-areas

### 4. Enable Detailed Logging

Set logging level to DEBUG to see more details:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Next Steps

1. **Run the debug script** with your PDF to see what's being extracted
2. **Compare the debug output** with your expected results
3. **Share the debug output** if you need further assistance
4. **Check the Excel file** to see the final formatted output

The improved parser should now handle:
- Different spacing patterns
- Various sub-area formats
- Multi-line entries
- Entries 1-9 with double-digit format
- Better error handling and recovery




