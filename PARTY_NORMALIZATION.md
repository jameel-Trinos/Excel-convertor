# Party Name Normalization

## Overview

The party name normalization feature automatically standardizes political party vote column names during PDF to Excel conversion. This ensures consistent naming across different documents, making data analysis and aggregation much easier.

**Specifically designed for Tamil Nadu election data.**

## Standardized Party Names

All party vote columns are normalized to these exact names:

| Standardized Name | Original Variations |
|-------------------|---------------------|
| `DMK Votes` | Dravida Munnetra Kazhagam, DMK, D.M.K., D M K |
| `AIADMK Votes` | All India Anna Dravida Munnetra Kazhagam, AIADMK, A.I.A.D.M.K., Anna DMK |
| `BJP Votes` | Bharatiya Janata Party, BJP, B.J.P., B J P |
| `Congress Votes` | Indian National Congress, Congress, INC, I.N.C., Congress (I) |
| `VCK Votes` | Viduthalai Chiruthaigal Katchi, VCK, V.C.K., V C K |
| `PMK Votes` | Pattali Makkal Katchi, PMK, P.M.K., P M K |
| `NTK Votes` | Naam Tamilar Katchi, NTK, N.T.K., N T K |
| `Other Votes` | Independent, NOTA, None of the Above, Others |

## How It Works

### Automatic Normalization

The normalization happens automatically during the AI column standardization phase:

1. **PDF Upload** - User uploads PDF with election data
2. **Table Extraction** - Tables are extracted with original column names
3. **AI Processing** - AI identifies column variations across pages
4. **Party Normalization** - Party names are mapped to standardized names
5. **Excel Output** - Final Excel file contains only standardized party column names

### Integration Points

Party normalization is integrated into both AI processors:

- **Claude Processor** ([claude_processor.py](backend/app/claude_processor.py:253)) - Primary AI processor
- **OpenAI Processor** ([ai_processor.py](backend/app/ai_processor.py:251)) - Fallback AI processor

The normalization is applied after AI column mapping but before Excel generation.

## Example Transformation

### Input (Original PDF Headers)

**Page 1:**
```
Serial No. | Candidate Name | DMK | AIADMK | BJP | Congress | Independent | Total
```

**Page 2:**
```
S.No. | Name | Dravida Munnetra Kazhagam | All India Anna Dravida Munnetra Kazhagam | Bharatiya Janata Party | INC | Other | Total Votes
```

### Output (Excel File Headers)

**Combined Excel:**
```
Serial Number | Candidate Name | DMK Votes | AIADMK Votes | BJP Votes | Congress Votes | Other Votes | Total Votes
```

## Advanced Features

### Fuzzy Matching

The normalizer supports intelligent matching:

- **Exact Match**: `DMK` → `DMK Votes`
- **Case Insensitive**: `dmk` → `DMK Votes`
- **With Dots**: `D.M.K.` → `DMK Votes`
- **With Spaces**: `D M K` → `DMK Votes`
- **Partial Match**: `Total Votes - DMK` → `DMK Votes`
- **Complex Names**: `Votes for Bharatiya Janata Party` → `BJP Votes`

### Non-Party Columns

Non-party columns are preserved unchanged:

- `Serial Number` - Unchanged
- `Candidate Name` - Unchanged
- `Total Votes` - Unchanged
- `Percentage` - Unchanged
- `Ward Number` - Unchanged

## Testing

Run the test suite to verify normalization:

```bash
cd backend
python3 test_party_normalizer.py
```

The test suite validates:
1. ✓ Basic party name normalization
2. ✓ Name variations and abbreviations
3. ✓ Partial matches in complex column names
4. ✓ Non-party columns are not modified
5. ✓ Integration with AI column mapping
6. ✓ Header list normalization
7. ✓ Standardized party name list

## Configuration

### Adding Custom Party Mappings

If you need to add support for additional parties:

```python
from app.party_normalizer import PartyNormalizer

normalizer = PartyNormalizer()

# Add custom party mapping
normalizer.add_custom_mapping(
    party_name="CPI Votes",
    variations=[
        "Communist Party of India",
        "CPI",
        "C.P.I.",
        "CPI (M)",
    ]
)
```

### Modifying Default Mappings

Edit the `PARTY_MAPPINGS` dictionary in [party_normalizer.py](backend/app/party_normalizer.py:26-57):

```python
PARTY_MAPPINGS = {
    "DMK Votes": [
        "Dravida Munnetra Kazhagam",
        "DMK",
        # Add more variations here
    ],
    # ... other parties
}
```

## API Reference

### PartyNormalizer Class

**Location**: [backend/app/party_normalizer.py](backend/app/party_normalizer.py)

#### Methods

**`normalize_column_name(column_name: str) -> Optional[str]`**

Normalize a single column name to standardized party name.

```python
normalizer = PartyNormalizer()
result = normalizer.normalize_column_name("DMK")
# Returns: "DMK Votes"
```

**`normalize_headers(headers: List[str]) -> List[str]`**

Normalize a complete list of column headers.

```python
original = ["S.No.", "Name", "DMK", "AIADMK", "Total"]
normalized = normalizer.normalize_headers(original)
# Returns: ["S.No.", "Name", "DMK Votes", "AIADMK Votes", "Total"]
```

**`normalize_column_mapping(column_mapping: Dict) -> Dict`**

Apply party normalization to AI-generated column mapping.

```python
ai_mapping = {
    "Dravida Munnetra Kazhagam": ["DMK", "D.M.K."],
    "All India Anna Dravida Munnetra Kazhagam": ["AIADMK"]
}
normalized = normalizer.normalize_column_mapping(ai_mapping)
# Returns: {
#     "DMK Votes": ["DMK", "D.M.K."],
#     "AIADMK Votes": ["AIADMK"]
# }
```

**`is_party_column(column_name: str) -> bool`**

Check if a column is a party vote column.

```python
is_party = normalizer.is_party_column("DMK")
# Returns: True
```

**`get_standardized_party_names() -> List[str]`**

Get the list of all standardized party names.

```python
parties = normalizer.get_standardized_party_names()
# Returns: ["DMK Votes", "AIADMK Votes", "BJP Votes", ...]
```

## Architecture

### Data Flow

```
PDF Upload
    ↓
Table Extraction (pdf_processor.py)
    ↓
AI Column Mapping (claude_processor.py / ai_processor.py)
    ↓
Party Normalization (party_normalizer.py) ← Applied here
    ↓
Excel Generation (excel_creator.py)
    ↓
Download Excel
```

### File Structure

- **[backend/app/party_normalizer.py](backend/app/party_normalizer.py)** - Core normalization logic
- **[backend/app/claude_processor.py](backend/app/claude_processor.py)** - Claude AI integration
- **[backend/app/ai_processor.py](backend/app/ai_processor.py)** - OpenAI integration
- **[backend/test_party_normalizer.py](backend/test_party_normalizer.py)** - Test suite

## Benefits

1. **Consistency** - Same party names across all Excel files
2. **Data Analysis** - Easy to aggregate and compare data
3. **Automation** - No manual column renaming needed
4. **Accuracy** - Handles variations, abbreviations, and complex names
5. **Extensible** - Easy to add new parties or variations

## Limitations

- Designed specifically for Tamil Nadu election data
- Requires AI processing to be enabled (ANTHROPIC_API_KEY or OPENAI_API_KEY)
- Custom parties need to be added manually via configuration
- Very complex or ambiguous column names may need manual review

## Future Enhancements

Potential improvements:

- Support for other Indian states' political parties
- Configuration file for party mappings (instead of hard-coded)
- UI for managing party mappings
- Machine learning-based party name detection
- Support for coalition names (e.g., "DMK Alliance")
