# Party Name Normalization Guide

## Overview

The Party Name Normalization feature automatically standardizes political party column names in election data PDFs and aggregates minor parties into a single "OTHERS" category. This ensures consistent naming across different PDF formats and makes data analysis easier.

## Features

✅ **Automatic Party Recognition**: Recognizes 40+ variations of party names  
✅ **Standardized Output**: Converts all party names to consistent format  
✅ **Intelligent Aggregation**: Groups minor parties into "OTHERS"  
✅ **Data Preservation**: No vote data is lost during normalization  
✅ **Claude AI Integration**: Works seamlessly with Anthropic's Claude for extraction

## Party Mapping

### Major Parties (Kept Separate)

| Original Name | Standardized Name |
|--------------|-------------------|
| Dravida Munnetra Kazhagam | **DMK** |
| All India Anna Dravida Munnetra Kazhagam | **AIADMK** |
| BHARATIYA JANATA PARTY / Bharatiya Janata Party | **BJP** |
| Indian National Congress | **CONGRESS** |
| VIDUTHALAI CHIRUTHAIGAL KATCHI / Viduthalai Chiruthaigal Katchi | **VCK** |
| PATTALI MAKKAL KATCHI / Pattali Makkal Katchi | **PMK** |
| NAAM TAMILAR KATCHI / Naam Tamilar Katchi | **NTK** |

### Minor Parties (Aggregated to OTHERS)

The following parties are automatically grouped into **OTHERS**:
- BSP (Bahujan Samaj Party)
- CPI (Communist Party of India)
- CPM (Communist Party of India - Marxist)
- MDMK (Marumalarchi Dravida Munnetra Kazhagam)
- NMK (Namma Makkal Katchi)
- Independent candidates
- NOTA (None of the Above)
- Any other unlisted parties

## How It Works

### 1. Column Name Recognition

The normalizer recognizes multiple formats:
- Full names: `Dravida Munnetra Kazhagam`
- Abbreviations: `DMK`, `D.M.K.`, `D M K`
- With suffixes: `DMK Votes`, `Dravida Munnetra Kazhagam Votes`
- Case-insensitive: `BHARATIYA JANATA PARTY`, `Bharatiya Janata Party`

### 2. Data Aggregation

When multiple minor party columns are found, their vote counts are summed:

**Before:**
```
| Station | DMK | AIADMK | BJP | BSP | CPI | Independent | NOTA |
|---------|-----|--------|-----|-----|-----|-------------|------|
| 001     | 500 | 450    | 200 | 30  | 25  | 40          | 10   |
```

**After:**
```
| Station | DMK | AIADMK | BJP | OTHERS |
|---------|-----|--------|-----|--------|
| 001     | 500 | 450    | 200 | 105    |
```

*Note: OTHERS = BSP(30) + CPI(25) + Independent(40) + NOTA(10) = 105*

## Usage

### Method 1: Command Line Script (Recommended)

```bash
# Make sure ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY='your-api-key-here'

# Convert PDF with party normalization
python3 convert_with_party_normalization.py election_data.pdf

# Or specify output file
python3 convert_with_party_normalization.py election_data.pdf output.xlsx
```

### Method 2: Python Code

```python
import asyncio
from app.enhanced_claude_processor import EnhancedClaudeProcessor
from app.excel_creator import ExcelCreator

async def convert_with_normalization(pdf_path, output_path):
    # Initialize Claude processor
    processor = EnhancedClaudeProcessor(api_key="your-api-key")
    
    # Extract with party normalization enabled
    tables, metadata = await processor.enhanced_extract(
        pdf_path,
        apply_party_normalization=True  # Enable normalization
    )
    
    # Create Excel
    creator = ExcelCreator()
    creator.create_from_tables(
        tables,
        output_path,
        source_filename=pdf_path,
        document_title=metadata.get("document_title", "")
    )

# Run conversion
asyncio.run(convert_with_normalization("input.pdf", "output.xlsx"))
```

### Method 3: API Endpoint

The party normalization is automatically applied when using the enhanced Claude mode:

```bash
# Upload and convert PDF
curl -X POST http://localhost:8000/convert \
  -F "file=@election_data.pdf" \
  -H "Content-Type: multipart/form-data"
```

## Testing

### Run Demo Script

To see party normalization in action without a PDF:

```bash
cd backend
python3 demo_party_normalization.py
```

This will show:
1. Basic party name normalization
2. Variations and abbreviations
3. Column aggregation with sample data
4. Complete header normalization
5. List of all standardized party names

### Run Unit Tests

```bash
cd backend
python3 test_party_normalizer.py
```

## Configuration

### Adding Custom Party Mappings

You can add custom party mappings programmatically:

```python
from app.party_normalizer import PartyNormalizer

normalizer = PartyNormalizer()

# Add a new regional party
normalizer.add_custom_mapping(
    party_name="REGIONAL_PARTY",
    variations=[
        "Regional Party Name",
        "RPP",
        "R.P.P.",
        "Regional Party Votes"
    ]
)
```

### Customizing OTHERS Category

To change which parties are grouped into OTHERS, edit `backend/app/party_normalizer.py`:

```python
PARTY_MAPPINGS = {
    # ... major parties ...
    "OTHERS": [
        "Your Party Name",
        "Another Party Name",
        # Add more here
    ]
}
```

## Output Format

The generated Excel file includes:

1. **Document Title**: Extracted from PDF (e.g., "FORM 20 - FINAL RESULT SHEET")
2. **Normalized Headers**: Standardized party names
3. **Aggregated Data**: Minor parties summed into OTHERS
4. **Professional Formatting**: Styled headers, borders, and alignment
5. **Metadata**: All non-party columns preserved (S.No., Polling Station, Total Votes, etc.)

### Example Output

```
┌─────────┬──────────────────┬─────┬────────┬─────┬──────────┬─────┬─────┬─────┬────────┬──────────────┐
│ S.No.   │ Polling Station  │ DMK │ AIADMK │ BJP │ CONGRESS │ VCK │ PMK │ NTK │ OTHERS │ Total Votes  │
├─────────┼──────────────────┼─────┼────────┼─────┼──────────┼─────┼─────┼─────┼────────┼──────────────┤
│ 1       │ Station 001      │ 500 │ 450    │ 200 │ 150      │ 100 │ 80  │ 50  │ 125    │ 1655         │
│ 2       │ Station 002      │ 520 │ 430    │ 210 │ 140      │ 95  │ 75  │ 55  │ 111    │ 1636         │
│ 3       │ Station 003      │ 510 │ 440    │ 205 │ 145      │ 98  │ 78  │ 52  │ 125    │ 1653         │
└─────────┴──────────────────┴─────┴────────┴─────┴──────────┴─────┴─────┴─────┴────────┴──────────────┘
```

## Benefits

1. **Consistency**: All PDFs produce the same column names
2. **Simplification**: Reduces 15+ columns to 8-10 meaningful columns
3. **Analysis-Ready**: Makes pivot tables and charts easier
4. **No Data Loss**: All votes are preserved and accurately counted
5. **Automatic**: Works without manual configuration

## Troubleshooting

### Party Not Recognized

If a party name is not being recognized:

1. Check the spelling in your PDF
2. Add the variation to `PARTY_MAPPINGS` in `party_normalizer.py`
3. Restart the server or re-run the script

### Incorrect Aggregation

If votes are being aggregated incorrectly:

1. Verify the party is listed under "OTHERS" in `PARTY_MAPPINGS`
2. Check that numeric values are being parsed correctly
3. Run the demo script to test the normalization logic

### API Key Issues

If you see "ANTHROPIC_API_KEY not configured":

1. Set the environment variable: `export ANTHROPIC_API_KEY='sk-...'`
2. Or add to `.env` file: `ANTHROPIC_API_KEY=sk-...`
3. Restart the backend server

## Architecture

```
┌─────────────────┐
│   PDF Input     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  Enhanced Claude Processor  │
│  - Extract tables           │
│  - Analyze structure        │
│  - Clean duplicates         │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   Party Normalizer          │
│  - Recognize party names    │
│  - Standardize columns      │
│  - Aggregate OTHERS         │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│   Excel Creator             │
│  - Format spreadsheet       │
│  - Apply styling            │
│  - Generate output          │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────┐
│  Excel Output   │
└─────────────────┘
```

## API Reference

### PartyNormalizer

#### Methods

##### `normalize_column_name(column_name: str) -> Optional[str]`
Normalize a single column name.

```python
normalizer = PartyNormalizer()
result = normalizer.normalize_column_name("Dravida Munnetra Kazhagam")
# Returns: "DMK"
```

##### `normalize_headers(headers: List[str]) -> List[str]`
Normalize a list of headers.

```python
headers = ["S.No.", "DMK", "AIADMK", "BSP", "Total"]
normalized = normalizer.normalize_headers(headers)
# Returns: ["S.No.", "DMK", "AIADMK", "OTHERS", "Total"]
```

##### `normalize_and_aggregate_columns(headers, data_rows) -> Tuple`
Normalize headers and aggregate data.

```python
headers = ["S.No.", "DMK", "BSP", "CPI"]
data = [["1", "500", "30", "25"]]

norm_headers, norm_data = normalizer.normalize_and_aggregate_columns(headers, data)
# Returns: (["S.No.", "DMK", "OTHERS"], [["1", "500", 55]])
```

## Support

For issues or questions:
1. Check the demo scripts: `demo_party_normalization.py`
2. Review test cases: `test_party_normalizer.py`
3. Check logs: `backend/backend.log`
4. Review the source: `backend/app/party_normalizer.py`

## License

This feature is part of the PDF to Excel Converter project.







